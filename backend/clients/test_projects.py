from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase

from fastapi import HTTPException

from api.routers.projects import require_project_creator, require_project_reader
from api.main import app
from api.routers.auth import hash_password
from fastapi.testclient import TestClient
from clients.models import Client, Collaborator, Project, Role, WebCatalog


class ProjectModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        web_type = WebCatalog.objects.create(
            name='Proyecto test', base_price_rent=10, base_price_sale=100
        )
        cls.client_record = Client.objects.create(
            name='Cliente test', document_type='DNI', document_number='TEST-PROJECT-1',
            web_type=web_type, plan='alquiler',
        )

    def test_project_defaults_to_planned_and_stores_optional_fields(self):
        project = Project.objects.create(client=self.client_record, name='Sitio institucional')

        self.assertEqual(project.status, 'Planificado')
        self.assertIsNone(project.objective)
        self.assertIsNone(project.scope)
        self.assertEqual(self.client_record.projects.get(), project)

    def test_database_rejects_status_outside_approved_catalog(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Project.objects.create(
                client=self.client_record, name='Estado inválido', status='Iniciado'
            )

    def test_client_cannot_be_physically_deleted_while_projects_exist(self):
        Project.objects.create(client=self.client_record, name='Protegido')

        with self.assertRaises(ProtectedError):
            self.client_record.delete()

    def test_project_permissions_match_approved_levels(self):
        require_project_creator({'role': 'L2'})
        require_project_reader({'role': 'L2'})
        require_project_reader({'role': 'L3'})
        with self.assertRaises(HTTPException) as create_error:
            require_project_creator({'role': 'L3'})
        self.assertEqual(create_error.exception.status_code, 403)
        with self.assertRaises(HTTPException) as read_error:
            require_project_reader({'role': 'L4'})
        self.assertEqual(read_error.exception.status_code, 403)

        for role in ('L1', 'L4', 'L5'):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as denied_create:
                    require_project_creator({'role': role})
                self.assertEqual(denied_create.exception.status_code, 403)
                with self.assertRaises(HTTPException) as denied_read:
                    require_project_reader({'role': role})
                self.assertEqual(denied_read.exception.status_code, 403)


class ProjectApiTests(TransactionTestCase):
    def setUp(self):
        role = Role.objects.create(name='Scrum Master', level='L2')
        Collaborator.objects.create(
            first_name='Proyecto', last_name='Prueba',
            document_number='PROJECT-API-1', email='project-api@example.com',
            username='project-api', password_hash=hash_password('test-password'),
            role=role,
        )
        web_type = WebCatalog.objects.create(
            name='Proyecto API', base_price_rent=10, base_price_sale=100,
        )
        self.client_record = Client.objects.create(
            name='Cliente API', document_type='DNI', document_number='PROJECT-CLIENT-1',
            web_type=web_type, plan='alquiler',
        )
        self.api = TestClient(app)
        login = self.api.post(
            '/api/auth/login',
            json={'username': 'project-api', 'password': 'test-password'},
        )
        self.headers = {'Authorization': f"Bearer {login.json()['access_token']}"}

    def test_create_and_read_project_through_api(self):
        created = self.api.post(
            '/api/projects/', headers=self.headers,
            json={'client_id': self.client_record.id, 'name': 'Proyecto API'},
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['status'], 'Planificado')
        self.assertEqual(created.json()['client_id'], self.client_record.id)
        self.assertEqual(
            self.api.get('/api/projects/', headers=self.headers).json(),
            [created.json()],
        )
        self.assertEqual(
            self.api.get(f"/api/projects/{created.json()['id']}", headers=self.headers).json(),
            created.json(),
        )

    def test_api_rejects_missing_client_and_blank_project_name(self):
        missing_client = self.api.post(
            '/api/projects/', headers=self.headers,
            json={'client_id': 999999, 'name': 'Proyecto'},
        )
        blank_name = self.api.post(
            '/api/projects/', headers=self.headers,
            json={'client_id': self.client_record.id, 'name': '   '},
        )

        self.assertEqual(missing_client.status_code, 404, missing_client.text)
        self.assertEqual(blank_name.status_code, 422, blank_name.text)

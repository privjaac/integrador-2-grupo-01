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

    def test_model_exposes_exact_official_status_catalog(self):
        self.assertEqual(
            [value for value, _label in Project.STATUS_CHOICES],
            ['Planificado', 'En ejecución', 'En validación técnica', 'Listo para entrega', 'Entregado'],
        )

    def test_project_defaults_to_planned_and_stores_optional_fields(self):
        project = Project.objects.create(client=self.client_record, name='Sitio institucional')

        self.assertEqual(project.status, 'Planificado')
        self.assertIsNone(project.objective)
        self.assertIsNone(project.scope)
        self.assertEqual(self.client_record.projects.get(), project)

    def test_database_rejects_status_outside_approved_catalog(self):
        for invalid_status in ('Iniciado', 'En progreso', 'En pausa', 'Completado', 'Cancelado'):
            with self.subTest(status=invalid_status):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Project.objects.create(
                        client=self.client_record, name='Estado inválido', status=invalid_status
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
        self.tokens = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'Rol proyecto {level}', level=level)
            Collaborator.objects.create(
                first_name='Proyecto', last_name=level,
                document_number=f'PROJECT-API-{level}', email=f'project-api-{level}@example.com',
                username=f'project-api-{level}', password_hash=hash_password('test-password'),
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
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            login = self.api.post(
                '/api/auth/login',
                json={'username': f'project-api-{level}', 'password': 'test-password'},
            )
            self.tokens[level] = {'Authorization': f"Bearer {login.json()['access_token']}"}
        self.headers = self.tokens['L2']

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
        invalid_initial_statuses = [
            self.api.post(
                '/api/projects/', headers=self.headers,
                json={'client_id': self.client_record.id, 'name': 'Estado no inicial', 'status': state},
            )
            for state in ('En ejecución', 'En validación técnica', 'Listo para entrega', 'Entregado',
                          'En progreso', 'En pausa', 'Completado', 'Cancelado')
        ]

        self.assertEqual(missing_client.status_code, 404, missing_client.text)
        self.assertEqual(blank_name.status_code, 422, blank_name.text)
        self.assertTrue(all(response.status_code == 422 for response in invalid_initial_statuses))

    def test_api_permissions_for_all_five_levels(self):
        project = Project.objects.create(client=self.client_record, name='Consulta autorizada')
        expected = {'L1': 403, 'L2': 200, 'L3': 200, 'L4': 403, 'L5': 403}
        for level, status_code in expected.items():
            with self.subTest(level=level):
                response = self.api.get('/api/projects/', headers=self.tokens[level])
                self.assertEqual(response.status_code, status_code, response.text)
                detail = self.api.get(f'/api/projects/{project.id}', headers=self.tokens[level])
                self.assertEqual(detail.status_code, status_code, detail.text)

        expected_create = {'L1': 403, 'L2': 201, 'L3': 403, 'L4': 403, 'L5': 403}
        for level, status_code in expected_create.items():
            with self.subTest(create_level=level):
                response = self.api.post(
                    '/api/projects/', headers=self.tokens[level],
                    json={'client_id': self.client_record.id, 'name': f'Creado por {level}'},
                )
                self.assertEqual(response.status_code, status_code, response.text)

    def test_api_rejects_inactive_client_without_creating_project(self):
        self.client_record.status = 'inactivo'
        self.client_record.save(update_fields=['status'])
        count_before = Project.objects.count()

        response = self.api.post(
            '/api/projects/', headers=self.headers,
            json={'client_id': self.client_record.id, 'name': 'No debe persistir'},
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(Project.objects.count(), count_before)

    def test_api_allows_non_inactive_commercial_statuses(self):
        for client_status in ('prospecto', 'activo', 'desarrollo'):
            with self.subTest(client_status=client_status):
                self.client_record.status = client_status
                self.client_record.save(update_fields=['status'])
                response = self.api.post(
                    '/api/projects/', headers=self.headers,
                    json={'client_id': self.client_record.id, 'name': f'Proyecto {client_status}'},
                )
                self.assertEqual(response.status_code, 201, response.text)

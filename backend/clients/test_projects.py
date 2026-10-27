from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from unittest.mock import patch

from fastapi import HTTPException

from api.routers.projects import require_project_creator, require_project_reader
from api.main import app
from api.routers.auth import hash_password
from fastapi.testclient import TestClient
from clients.models import Client, Collaborator, Project, ProjectCoordination, ProjectEvent, Role, WebCatalog


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

    @staticmethod
    def validation_payload(**overrides):
        payload = {
            'scope_within_current_commitment': True,
            'criteria_identifiable': True,
            'results_and_evidence_available': True,
            'validation_conditions_ready': True,
            'responsible_parties_identified': True,
            'dependencies_ready': True,
            'pending_obligations_assessed': True,
            'evidence': 'Informe técnico disponible para la evaluación',
            'reason': 'Preparación suficiente para iniciar validación',
        }
        payload.update(overrides)
        return payload

    def test_l3_enters_technical_validation_with_active_scope_and_complete_evidence(self):
        project = Project.objects.create(client=self.client_record, name='Validación', status='En ejecución')
        coordinator = Collaborator.objects.get(username='project-api-L3')
        ProjectCoordination.objects.create(
            project=project, coordinator=coordinator,
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )
        response = self.api.post(
            f'/api/projects/{project.id}/technical-validation',
            headers=self.tokens['L3'], json=self.validation_payload(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'En validación técnica')
        event = ProjectEvent.objects.get(project=project)
        self.assertEqual(event.event_type, 'ingreso_validacion_tecnica')
        self.assertEqual(event.actor_id, coordinator.id)
        self.assertEqual((event.previous_status, event.new_status), ('En ejecución', 'En validación técnica'))
        self.assertIn('Criterios identificables: sí', event.evidence)

    def test_validation_transition_denies_invalid_role_scope_origin_and_evidence(self):
        project = Project.objects.create(client=self.client_record, name='Fuera de ámbito', status='En ejecución')
        payload = self.validation_payload()
        for level in ('L1', 'L2', 'L4', 'L5'):
            response = self.api.post(
                f'/api/projects/{project.id}/technical-validation',
                headers=self.tokens[level], json=payload,
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual(ProjectEvent.objects.count(), 0)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')

        coordinator = Collaborator.objects.get(username='project-api-L3')
        l2 = Collaborator.objects.get(username='project-api-L2')
        coordination = ProjectCoordination.objects.create(project=project, coordinator=coordinator, assigned_by=l2)
        ProjectCoordination.objects.filter(pk=coordination.pk).update(is_active=False)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/technical-validation', headers=self.tokens['L3'], json=payload,
        ).status_code, 404)
        ProjectCoordination.objects.filter(pk=coordination.pk).update(is_active=True)
        project.status = 'Planificado'
        project.save(update_fields=['status'])
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/technical-validation', headers=self.tokens['L3'], json=payload,
        ).status_code, 409)
        project.status = 'En ejecución'
        project.save(update_fields=['status'])
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/technical-validation', headers=self.tokens['L3'],
            json=self.validation_payload(criteria_identifiable=False),
        ).status_code, 409)
        self.assertEqual(ProjectEvent.objects.count(), 0)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')

    def test_failed_project_event_write_rolls_back_status_transition(self):
        project = Project.objects.create(client=self.client_record, name='Rollback', status='En ejecución')
        ProjectCoordination.objects.create(
            project=project, coordinator=Collaborator.objects.get(username='project-api-L3'),
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )
        with patch('api.routers.projects.ProjectEvent.objects.create', side_effect=IntegrityError):
            response = self.api.post(
                f'/api/projects/{project.id}/technical-validation', headers=self.tokens['L3'],
                json=self.validation_payload(),
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')
        self.assertEqual(ProjectEvent.objects.count(), 0)

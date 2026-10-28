from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException

from api.routers.projects import require_project_creator, require_project_reader
from api.main import app
from api.routers.auth import hash_password
from fastapi.testclient import TestClient
from clients.models import (Client, Collaborator, InternalNotification, Project, ProjectCommercialAuthorization,
                            ProjectCommercialAuthorizationEvent, ProjectCoordination,
                            ProjectCancellation, ProjectCancellationEvent,
                            ProjectDeliveryAuthorization, ProjectDeliveryAuthorizationEvent,
                            ProjectDelivery, ProjectDeliveryTechnicalReview, ProjectDeliveryTransition,
                            ProjectEvent, ProjectTaskClassification, ProjectTechnicalEvaluation,
                            Role, Task, TaskEvent, WebCatalog)


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

    @staticmethod
    def return_payload(**overrides):
        payload = {
            'additional_execution_required': True,
            'materially_affects_validation': True,
            'within_current_commitment': True,
            'evidence': 'Hallazgo técnico que requiere trabajo adicional',
            'reason': 'Se requiere completar el alcance comprometido antes de continuar la validación',
        }
        payload.update(overrides)
        return payload

    def test_l3_returns_technical_validation_to_execution_with_audit(self):
        project = Project.objects.create(client=self.client_record, name='Devolución', status='En validación técnica')
        coordinator = Collaborator.objects.get(username='project-api-L3')
        ProjectCoordination.objects.create(
            project=project, coordinator=coordinator,
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )

        response = self.api.post(
            f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'],
            json=self.return_payload(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'En ejecución')
        event = ProjectEvent.objects.get(project=project)
        self.assertEqual(event.event_type, 'devolucion_ejecucion')
        self.assertEqual(event.actor_id, coordinator.id)
        self.assertEqual((event.previous_status, event.new_status), ('En validación técnica', 'En ejecución'))
        self.assertIn('Afecta materialmente suficiencia/continuidad de validación: sí', event.evidence)

    def test_return_denies_other_roles_missing_scope_wrong_state_and_incomplete_conditions(self):
        project = Project.objects.create(client=self.client_record, name='Denegación devolución', status='En validación técnica')
        payload = self.return_payload()
        for level in ('L1', 'L2', 'L4', 'L5'):
            response = self.api.post(
                f'/api/projects/{project.id}/return-to-execution', headers=self.tokens[level], json=payload,
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'], json=payload,
        ).status_code, 404)

        coordinator = Collaborator.objects.get(username='project-api-L3')
        coordination = ProjectCoordination.objects.create(
            project=project, coordinator=coordinator,
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )
        coordination.is_active = False
        coordination.save(update_fields=['is_active'])
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'], json=payload,
        ).status_code, 404)
        coordination.is_active = True
        coordination.save(update_fields=['is_active'])
        for overrides in ({'additional_execution_required': False}, {'within_current_commitment': False}):
            response = self.api.post(
                f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'],
                json=self.return_payload(**overrides),
            )
            self.assertEqual(response.status_code, 409, response.text)
        project.status = 'En ejecución'
        project.save(update_fields=['status'])
        response = self.api.post(
            f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'], json=payload,
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(ProjectEvent.objects.count(), 0)

    def test_failed_return_event_write_rolls_back_status_transition(self):
        project = Project.objects.create(client=self.client_record, name='Rollback devolución', status='En validación técnica')
        ProjectCoordination.objects.create(
            project=project, coordinator=Collaborator.objects.get(username='project-api-L3'),
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )
        with patch('api.routers.projects.ProjectEvent.objects.create', side_effect=IntegrityError):
            response = self.api.post(
                f'/api/projects/{project.id}/return-to-execution', headers=self.tokens['L3'],
                json=self.return_payload(),
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')
        self.assertEqual(ProjectEvent.objects.count(), 0)

    @staticmethod
    def start_payload(authorization_id, **overrides):
        payload = {
            'commercial_authorization_id': authorization_id,
            'initial_activities': 'Planificación y configuración inicial',
            'initial_scope_within_authorization': True,
            'responsible_parties_identified': True,
            'resources_ready': True,
            'dependencies_ready': True,
            'restrictions_assessed': True,
            'reason': 'Inicio autorizado con preparación suficiente',
            'evidence': 'Acta técnica inicial',
        }
        payload.update(overrides)
        return payload

    def create_authorization(self, project, **overrides):
        payload = {
            'authorized_scope': 'Sitio institucional y módulos acordados',
            'commitment_reference': 'COMP-2026-41',
            'start_conditions': 'Condiciones de inicio revisadas y acreditadas',
            'start_conditions_accredited': True,
            'evidence_reference': 'EXP-41/ANEXO-2',
            'effective_at': (timezone.now() + timedelta(minutes=2)).isoformat(),
        }
        payload.update(overrides)
        return self.api.post(
            f'/api/projects/{project.id}/commercial-authorizations',
            headers=self.tokens['L2'], json=payload,
        )

    def coordinate_l3(self, project):
        return ProjectCoordination.objects.create(
            project=project,
            coordinator=Collaborator.objects.get(username='project-api-L3'),
            assigned_by=Collaborator.objects.get(username='project-api-L2'),
        )

    def open_project_cancellation(self, project, **overrides):
        payload = {
            'cancelled_scope': project.scope,
            'reason': 'El cliente solicita terminar integralmente el proyecto',
            'evidence': 'Solicitud comercial DOC-CANCEL-01',
        }
        payload.update(overrides)
        return self.api.post(
            f'/api/projects/{project.id}/cancellations', headers=self.tokens['L2'], json=payload,
        )

    def evaluate_project_cancellation_commercially(self, project, cancellation_id, **overrides):
        payload = {
            'within_l2_competence': True,
            'commercial_consequences': 'Compromisos revisados; sin efectos financieros automáticos',
            'effectivity_conditions': 'Condiciones aplicables documentadas',
            'evidence': 'Evaluación comercial EC-01',
        }
        payload.update(overrides)
        return self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/commercial-evaluation',
            headers=self.tokens['L2'], json=payload,
        )

    def test_project_cancellation_requires_l2_scope_l3_review_and_effective_conditions(self):
        project = Project.objects.create(
            client=self.client_record, name='Cancelación ordinaria', scope='Módulos A y B',
            status='En ejecución',
        )
        self.coordinate_l3(project)
        Task.objects.create(
            project=project, title='Tarea conserva estado',
            created_by=Collaborator.objects.get(username='project-api-L2'),
            responsible=Collaborator.objects.get(username='project-api-L4'),
        )

        wrong_scope = self.open_project_cancellation(project, cancelled_scope='Solo módulo A')
        self.assertEqual(wrong_scope.status_code, 409, wrong_scope.text)
        self.assertEqual(ProjectCancellation.objects.count(), 0)
        forbidden_request = self.api.post(
            f'/api/projects/{project.id}/cancellations', headers=self.tokens['L3'],
            json={'cancelled_scope': project.scope, 'reason': 'Solicitar', 'evidence': 'Evidencia'},
        )
        self.assertEqual(forbidden_request.status_code, 403)
        invalid_scope_actor = Collaborator.objects.create(
            first_name='Proyecto', last_name='L2 restringido', document_number='PROJECT-API-L2-RESTRICTED',
            email='project-api-l2-restricted@example.com', username='project-api-L2-restricted',
            password_hash=hash_password('test'), role=Role.objects.create(
                name='Rol L2 sin permiso de cancelación', level='L2',
                permissions=['projects.view'],
            ),
        )
        restricted_token = self.api.post('/api/auth/login', json={
            'username': invalid_scope_actor.username, 'password': 'test',
        }).json()['access_token']
        restricted = self.api.post(
            f'/api/projects/{project.id}/cancellations',
            headers={'Authorization': f'Bearer {restricted_token}'},
            json={'cancelled_scope': project.scope, 'reason': 'Solicitar', 'evidence': 'Evidencia'},
        )
        self.assertEqual(restricted.status_code, 403)
        self.assertEqual(ProjectCancellation.objects.count(), 0)

        requested = self.open_project_cancellation(project)
        self.assertEqual(requested.status_code, 201, requested.text)
        cancellation_id = requested.json()['id']
        denied_without_review = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Autorizar', 'evidence': 'Acta',
                'commercial_consequences': 'Evaluadas', 'effectivity_conditions': 'Acta firmada',
                'planned_effective_at': timezone.now().isoformat(),
            },
        )
        self.assertEqual(denied_without_review.status_code, 409)

        no_coordination = Project.objects.create(
            client=self.client_record, name='Proyecto fuera de coordinación', scope='Alcance completo',
        )
        no_coordination_case = self.open_project_cancellation(no_coordination)
        self.assertEqual(no_coordination_case.status_code, 201, no_coordination_case.text)
        outside_scope = self.api.post(
            f"/api/projects/{no_coordination.id}/cancellations/{no_coordination_case.json()['id']}/technical-evaluation",
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Tareas revisadas',
                'obligations_assessment': 'Obligaciones identificadas', 'evidence': 'Informe técnico',
                'l1_intervention_required': False,
            },
        )
        self.assertEqual(outside_scope.status_code, 404)
        self.assertEqual(ProjectCancellationEvent.objects.filter(
            cancellation_id=no_coordination_case.json()['id'], event_type='evaluacion_tecnica',
        ).count(), 0)

        evaluated = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Se identificaron y conservaron los estados de las tareas',
                'obligations_assessment': 'Compromisos y obligaciones residuales evaluados',
                'evidence': 'Informe técnico de cancelación',
                'l1_intervention_required': False,
            },
        )
        self.assertEqual(evaluated.status_code, 200, evaluated.text)
        self.assertEqual(project.status, 'En ejecución')
        self.assertIn('task_snapshot', evaluated.json()['events'][-1]['data'])

        unrelated_task = Task.objects.create(
            project=project, title='Aviso urgente ajeno al caso',
            created_by=Collaborator.objects.get(username='project-api-L2'),
            responsible=Collaborator.objects.get(username='project-api-L4'),
        )
        InternalNotification.objects.create(
            task=unrelated_task, recipient=Collaborator.objects.get(username='project-api-L2'),
            notice_type='urgent', title='Aviso urgente no relacionado',
            message='Este aviso no solicita intervención L1 en la cancelación actual',
        )
        commercial = self.evaluate_project_cancellation_commercially(
            project, cancellation_id,
            commercial_consequences='Compromisos revisados; no se ordenan pagos ni devoluciones',
            effectivity_conditions='La condición documentada está satisfecha',
        )
        self.assertEqual(commercial.status_code, 200, commercial.text)
        self.assertEqual(commercial.json()['events'][-1]['event_type'], 'evaluacion_comercial')

        decided = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Formalización comercial ordinaria',
                'evidence': 'Acta comercial AC-01',
                'commercial_consequences': 'Compromisos revisados; no se ordenan pagos ni devoluciones',
                'effectivity_conditions': 'La condición documentada está satisfecha',
                'planned_effective_at': (timezone.now() + timedelta(seconds=2)).isoformat(),
            },
        )
        self.assertEqual(decided.status_code, 200, decided.text)
        self.assertEqual(decided.json()['events'][-1]['event_type'], 'autorizada')
        persisted_events = list(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id,
        ).order_by('id'))
        self.assertEqual([event.event_type for event in persisted_events], [
            'solicitada', 'evaluacion_tecnica', 'evaluacion_comercial', 'autorizada',
        ])
        self.assertIn('task_snapshot', persisted_events[1].data)
        project.refresh_from_db()
        self.assertEqual(project.status, 'En ejecución')
        self.assertEqual(ProjectEvent.objects.filter(project=project).count(), 3)
        with patch('api.routers.projects.timezone.now', return_value=timezone.now() + timedelta(seconds=3)):
            effective = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/effectivity',
            headers=self.tokens['L2'], json={
                'conditions_satisfied': True, 'reason': 'Condiciones satisfechas', 'evidence': 'EV-EFFECT',
            },
            )
        self.assertEqual(effective.status_code, 200, effective.text)
        effective_event = ProjectCancellationEvent.objects.get(cancellation_id=cancellation_id, event_type='efectiva')
        self.assertEqual(effective_event.actor_id, Collaborator.objects.get(username='project-api-L2').id)
        self.assertIsNotNone(effective_event.effective_at)
        self.assertEqual(ProjectEvent.objects.filter(project=project).count(), 4)
        project.refresh_from_db()
        self.assertEqual(project.status, 'En ejecución')
        self.assertEqual(Task.objects.get(pk=unrelated_task.id).status, 'Pendiente')
        with patch('api.routers.tasks.timezone.now', return_value=effective_event.effective_at + timedelta(seconds=1)):
            blocked_task = self.api.post('/api/tasks/', headers=self.tokens['L3'], json={
                'project_id': project.id, 'title': 'Nueva tarea luego de cancelación efectiva', 'status': 'Pendiente',
            })
        self.assertEqual(blocked_task.status_code, 409, blocked_task.text)

    def test_project_cancellation_future_effectivity_and_denial_preserve_history(self):
        project = Project.objects.create(
            client=self.client_record, name='Cancelación futura', scope='Alcance completo',
        )
        self.coordinate_l3(project)
        requested = self.open_project_cancellation(project)
        cancellation_id = requested.json()['id']
        self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Tareas analizadas',
                'obligations_assessment': 'Obligaciones conservadas', 'evidence': 'EV-1',
                'l1_intervention_required': False,
            },
        )
        commercial = self.evaluate_project_cancellation_commercially(
            project, cancellation_id, commercial_consequences='Evaluadas', effectivity_conditions='Fecha acordada',
        )
        self.assertEqual(commercial.status_code, 200, commercial.text)
        future = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Autorizar fecha futura', 'evidence': 'AC-2',
                'commercial_consequences': 'Evaluadas', 'effectivity_conditions': 'Fecha acordada',
                'planned_effective_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(future.status_code, 200, future.text)
        self.assertTrue(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id, event_type='autorizada',
        ).exists())
        premature = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/effectivity',
            headers=self.tokens['L2'], json={
                'conditions_satisfied': True, 'reason': 'Intento prematuro', 'evidence': 'EV-2',
            },
        )
        self.assertEqual(premature.status_code, 409)
        self.assertFalse(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id, event_type='efectiva',
        ).exists())

        denied_project = Project.objects.create(
            client=self.client_record, name='Cancelación denegada', scope='Alcance completo',
        )
        self.coordinate_l3(denied_project)
        denied_case = self.open_project_cancellation(denied_project)
        self.api.post(
            f"/api/projects/{denied_project.id}/cancellations/{denied_case.json()['id']}/technical-evaluation",
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Tareas evaluadas',
                'obligations_assessment': 'Obligaciones evaluadas', 'evidence': 'EV-DENY',
                'l1_intervention_required': False,
            },
        )
        denial = self.api.post(
            f"/api/projects/{denied_project.id}/cancellations/{denied_case.json()['id']}/decision",
            headers=self.tokens['L2'], json={
                'authorized': False, 'reason': 'No corresponde cancelar', 'evidence': 'Análisis comercial',
            },
        )
        self.assertEqual(denial.status_code, 200, denial.text)
        self.assertEqual(ProjectCancellation.objects.filter(project=denied_project).count(), 1)
        denied_events = list(ProjectCancellationEvent.objects.filter(
            cancellation_id=denied_case.json()['id'],
        ).order_by('id'))
        self.assertEqual([event.event_type for event in denied_events], [
            'solicitada', 'evaluacion_tecnica', 'denegada',
        ])
        self.assertEqual(denied_events[-1].actor.username, 'project-api-L2')
        self.assertEqual(ProjectEvent.objects.filter(project=denied_project).count(), 3)
        self.assertFalse(ProjectCancellationEvent.objects.filter(
            cancellation_id=denied_case.json()['id'], event_type='efectiva',
        ).exists())

    def test_l3_documented_exception_blocks_l2_and_cannot_be_overridden(self):
        project = Project.objects.create(
            client=self.client_record, name='Excepción técnica L1', status='En ejecución', scope='Alcance completo',
        )
        self.coordinate_l3(project)
        requested = self.open_project_cancellation(project)
        cancellation_id = requested.json()['id']
        technical = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Evaluación técnica completa',
                'obligations_assessment': 'Obligaciones identificadas', 'evidence': 'Informe técnico EX-1',
                'l1_intervention_required': True, 'l1_exception_reason': 'Impacto fuera del tratamiento ordinario',
            },
        )
        self.assertEqual(technical.status_code, 200, technical.text)
        commercial = self.evaluate_project_cancellation_commercially(project, cancellation_id)
        self.assertEqual(commercial.status_code, 200, commercial.text)
        attempt = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Intento de autorización', 'evidence': 'ACTA-EX-1',
                'commercial_consequences': 'Compromisos revisados; sin efectos financieros automáticos',
                'effectivity_conditions': 'Condiciones aplicables documentadas',
                'planned_effective_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(attempt.status_code, 409, attempt.text)
        self.assertIn('requiere intervención L1', attempt.json()['detail'])
        self.assertEqual(
            list(ProjectCancellationEvent.objects.filter(cancellation_id=cancellation_id).values_list('event_type', flat=True)),
            ['solicitada', 'evaluacion_tecnica', 'evaluacion_comercial'],
        )
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')

    def test_l2_commercial_overreach_is_historical_and_blocks_self_override(self):
        project = Project.objects.create(
            client=self.client_record, name='Exceso comercial L2', status='En ejecución', scope='Alcance completo',
        )
        self.coordinate_l3(project)
        requested = self.open_project_cancellation(project)
        cancellation_id = requested.json()['id']
        technical = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Sin excepción técnica identificada',
                'obligations_assessment': 'Obligaciones revisadas', 'evidence': 'Informe técnico OK',
                'l1_intervention_required': False,
            },
        )
        self.assertEqual(technical.status_code, 200, technical.text)
        commercial = self.evaluate_project_cancellation_commercially(
            project, cancellation_id, within_l2_competence=False,
            commercial_consequences='Consecuencias fuera de facultades L2',
        )
        self.assertEqual(commercial.status_code, 200, commercial.text)
        self.assertEqual(commercial.json()['events'][-1]['event_type'], 'escalamiento_l1')
        override = self.evaluate_project_cancellation_commercially(project, cancellation_id)
        self.assertEqual(override.status_code, 409, override.text)
        attempt = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Intento de normalización', 'evidence': 'ACTA-OVERRIDE',
                'commercial_consequences': 'Compromisos revisados; sin efectos financieros automáticos',
                'effectivity_conditions': 'Condiciones aplicables documentadas',
                'planned_effective_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(attempt.status_code, 409, attempt.text)
        self.assertFalse(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id, event_type='autorizada',
        ).exists())

    def test_formal_linked_l1_escalation_blocks_authorization_and_is_idempotent(self):
        project = Project.objects.create(
            client=self.client_record, name='Comunicación L1', status='En ejecución', scope='Alcance completo',
        )
        self.coordinate_l3(project)
        requested = self.open_project_cancellation(project)
        cancellation_id = requested.json()['id']
        technical = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Sin excepción técnica conocida',
                'obligations_assessment': 'Obligaciones evaluadas', 'evidence': 'Informe técnico',
                'l1_intervention_required': False,
            },
        )
        self.assertEqual(technical.status_code, 200, technical.text)
        commercial = self.evaluate_project_cancellation_commercially(project, cancellation_id)
        self.assertEqual(commercial.status_code, 200, commercial.text)
        escalation_payload = {
            'reason': 'Comunicación solicita intervención L1',
            'source_origin': 'Documento recibido e incorporado al expediente',
            'source_reference': 'DOC-L1-2026-01',
            'received_at': timezone.now().isoformat(),
            'evidence': 'Expediente/ANEXO-L1-01',
        }
        route = f'/api/projects/{project.id}/cancellations/{cancellation_id}/escalations/l1'
        escalated = self.api.post(route, headers=self.tokens['L2'], json=escalation_payload)
        self.assertEqual(escalated.status_code, 200, escalated.text)
        event = ProjectCancellationEvent.objects.get(cancellation_id=cancellation_id, event_type='escalamiento_l1')
        self.assertEqual(event.actor.username, 'project-api-L2')
        self.assertEqual(event.data['source_reference'], 'DOC-L1-2026-01')
        duplicate = self.api.post(route, headers=self.tokens['L2'], json=escalation_payload)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        forbidden_l3_escalation = self.api.post(route, headers=self.tokens['L3'], json={
            **escalation_payload, 'source_reference': 'DOC-L1-L3-UNAUTHORIZED',
        })
        self.assertEqual(forbidden_l3_escalation.status_code, 403, forbidden_l3_escalation.text)
        attempt = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'No se puede superar el escalamiento', 'evidence': 'ACTA-ESC',
                'commercial_consequences': 'Compromisos revisados; sin efectos financieros automáticos',
                'effectivity_conditions': 'Condiciones aplicables documentadas',
                'planned_effective_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(attempt.status_code, 409, attempt.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')
        self.assertFalse(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id, event_type='autorizada',
        ).exists())

    def test_escalation_and_authorization_orders_keep_effectivity_blocked(self):
        project = Project.objects.create(
            client=self.client_record, name='Orden autorización y escalamiento',
            status='En ejecución', scope='Alcance completo',
        )
        self.coordinate_l3(project)
        requested = self.open_project_cancellation(project)
        cancellation_id = requested.json()['id']
        self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Sin excepción técnica',
                'obligations_assessment': 'Obligaciones evaluadas', 'evidence': 'EV-ORDER',
                'l1_intervention_required': False,
            },
        )
        self.evaluate_project_cancellation_commercially(project, cancellation_id)
        decision_body = {
            'authorized': True, 'reason': 'Autorización anterior al aviso', 'evidence': 'ACTA-ORDER',
            'commercial_consequences': 'Compromisos revisados; sin efectos financieros automáticos',
            'effectivity_conditions': 'Condiciones aplicables documentadas',
            'planned_effective_at': (timezone.now() + timedelta(hours=1)).isoformat(),
        }
        authorized = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/decision',
            headers=self.tokens['L2'], json=decision_body,
        )
        self.assertEqual(authorized.status_code, 200, authorized.text)
        escalation = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/escalations/l1',
            headers=self.tokens['L2'], json={
                'reason': 'Llegó solicitud formal de intervención L1',
                'source_origin': 'Expediente del proyecto', 'source_reference': 'DOC-ORDER-01',
                'received_at': timezone.now().isoformat(), 'evidence': 'EXP-ORDER-ANEXO-01',
            },
        )
        self.assertEqual(escalation.status_code, 200, escalation.text)
        effective = self.api.post(
            f'/api/projects/{project.id}/cancellations/{cancellation_id}/effectivity',
            headers=self.tokens['L2'], json={
                'conditions_satisfied': True, 'reason': 'Intento posterior al escalamiento', 'evidence': 'EV-ORDER-2',
            },
        )
        self.assertEqual(effective.status_code, 409, effective.text)
        self.assertEqual(
            list(ProjectCancellationEvent.objects.filter(cancellation_id=cancellation_id).values_list('event_type', flat=True)),
            ['solicitada', 'evaluacion_tecnica', 'evaluacion_comercial', 'autorizada', 'escalamiento_l1'],
        )
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')
        self.assertFalse(ProjectCancellationEvent.objects.filter(
            cancellation_id=cancellation_id, event_type='efectiva',
        ).exists())

    def test_l2_authorization_and_scoped_l3_start_are_explicit_and_historical(self):
        project = Project.objects.create(client=self.client_record, name='Inicio B4-09')
        self.coordinate_l3(project)
        authorized = self.create_authorization(project)
        self.assertEqual(authorized.status_code, 201, authorized.text)
        auth_id = authorized.json()['id']
        # Make its effectivity immediate in the test fixture.
        ProjectCommercialAuthorization.objects.filter(pk=auth_id).update(effective_at=timezone.now() - timedelta(seconds=1))
        l3_list = self.api.get(f'/api/projects/{project.id}/commercial-authorizations', headers=self.tokens['L3'])
        self.assertEqual(l3_list.status_code, 200, l3_list.text)
        self.assertEqual([row['id'] for row in l3_list.json()], [auth_id])
        self.assertNotIn('commitment_reference', l3_list.json()[0])
        started = self.api.post(
            f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
            json=self.start_payload(auth_id),
        )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()['status'], 'En ejecución')
        event = ProjectEvent.objects.get(project=project)
        self.assertEqual(event.commercial_authorization_id, auth_id)
        self.assertEqual((event.actor.role.level, event.previous_status, event.new_status),
                         ('L3', 'Planificado', 'En ejecución'))
        self.assertEqual(ProjectCommercialAuthorizationEvent.objects.count(), 0)
        withdrawn = self.api.post(
            f'/api/projects/{project.id}/commercial-authorizations/{auth_id}/withdrawal',
            headers=self.tokens['L2'], json={'reason': 'Cambio posterior de condiciones'},
        )
        self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En ejecución')
        self.assertEqual(ProjectEvent.objects.get(project=project).commercial_authorization_id, auth_id)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
            json=self.start_payload(auth_id),
        ).status_code, 409)

    def test_start_rejects_missing_wrong_project_future_expired_and_closed_authorization(self):
        project = Project.objects.create(client=self.client_record, name='Proyecto inicio')
        other = Project.objects.create(client=self.client_record, name='Proyecto ajeno')
        self.coordinate_l3(project)
        foreign = self.create_authorization(other)
        self.assertEqual(foreign.status_code, 201, foreign.text)
        unauthorized = self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                                     json=self.start_payload(foreign.json()['id']))
        self.assertEqual(unauthorized.status_code, 409)
        self.assertEqual(self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                                       json=self.start_payload(999999)).status_code, 409)
        for field, value in [('effective_at', timezone.now() + timedelta(days=1)),
                             ('expires_at', timezone.now() - timedelta(days=1))]:
            options = {'effective_at': (timezone.now() + timedelta(minutes=2)).isoformat()}
            options[field] = value.isoformat()
            if field == 'expires_at':
                options['effective_at'] = (timezone.now() + timedelta(minutes=1)).isoformat()
                options['expires_at'] = (timezone.now() + timedelta(minutes=2)).isoformat()
            created = self.create_authorization(project, **options)
            self.assertEqual(created.status_code, 201, created.text)
            if field == 'expires_at':
                ProjectCommercialAuthorization.objects.filter(pk=created.json()['id']).update(
                    effective_at=timezone.now() - timedelta(days=2),
                    expires_at=timezone.now() - timedelta(days=1),
                )
            response = self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                                     json=self.start_payload(created.json()['id']))
            self.assertEqual(response.status_code, 409)
        auth = self.create_authorization(project, effective_at=(timezone.now() + timedelta(minutes=2)).isoformat())
        auth_id = auth.json()['id']
        ProjectCommercialAuthorization.objects.filter(pk=auth_id).update(
            effective_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/commercial-authorizations/{auth_id}/withdrawal',
            headers=self.tokens['L2'], json={'reason': 'Se retiró el alcance aprobado'},
        ).status_code, 200)
        self.assertEqual(self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                                       json=self.start_payload(auth_id)).status_code, 409)
        self.assertEqual(ProjectEvent.objects.count(), 0)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Planificado')

    def test_authorization_roles_conditions_coordination_and_atomic_start(self):
        project = Project.objects.create(client=self.client_record, name='Permisos inicio')
        denied_auth = self.api.post(
            f'/api/projects/{project.id}/commercial-authorizations', headers=self.tokens['L3'],
            json={'authorized_scope': 'X', 'commitment_reference': 'X', 'start_conditions': 'X',
                  'start_conditions_accredited': True,
                  'evidence_reference': 'X', 'effective_at': (timezone.now()+timedelta(minutes=2)).isoformat()},
        )
        self.assertEqual(denied_auth.status_code, 403)
        future = self.create_authorization(project)
        auth_id = future.json()['id']
        self.assertEqual(self.api.get(f'/api/projects/{project.id}/commercial-authorizations',
                                      headers=self.tokens['L4']).status_code, 403)
        self.assertEqual(self.api.get(f'/api/projects/{project.id}/commercial-authorizations',
                                      headers=self.tokens['L3']).status_code, 404)
        self.coordinate_l3(project)
        ProjectCommercialAuthorization.objects.filter(pk=auth_id).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        # Scope mismatch and incomplete technical readiness reject before writes.
        mismatch = self.api.post(
            f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
            json=self.start_payload(auth_id, initial_scope_within_authorization=False),
        )
        self.assertEqual(mismatch.status_code, 409)
        payload = self.start_payload(auth_id, resources_ready=False)
        response = self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'], json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Planificado')
        self.assertEqual(ProjectEvent.objects.count(), 0)
        pending_conditions = self.create_authorization(
            project, start_conditions_accredited=False,
        )
        self.assertEqual(pending_conditions.status_code, 409)
        self.assertEqual(ProjectCommercialAuthorization.objects.filter(project=project).count(), 1)
        ProjectCoordination.objects.filter(project=project).update(is_active=False)
        self.assertEqual(self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                                       json=self.start_payload(auth_id)).status_code, 404)
        for level in ('L1', 'L2', 'L4', 'L5'):
            self.assertEqual(self.api.post(f'/api/projects/{project.id}/start', headers=self.tokens[level],
                                           json=self.start_payload(auth_id)).status_code, 403)

    def test_replacement_preserves_prior_authorization_and_failed_transition_is_atomic(self):
        project = Project.objects.create(client=self.client_record, name='Historial de habilitación')
        self.coordinate_l3(project)
        original = self.create_authorization(project)
        self.assertEqual(original.status_code, 201, original.text)
        replacement = self.create_authorization(
            project, replaces_authorization_id=original.json()['id'],
            replacement_reason='El alcance autorizado fue actualizado',
        )
        self.assertEqual(replacement.status_code, 201, replacement.text)
        prior_event = ProjectCommercialAuthorizationEvent.objects.get(authorization_id=original.json()['id'])
        self.assertEqual(prior_event.event_type, 'sustituida')
        self.assertEqual(prior_event.replacement_id, replacement.json()['id'])
        self.assertEqual(ProjectCommercialAuthorization.objects.count(), 2)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
            json=self.start_payload(original.json()['id']),
        ).status_code, 409)
        ProjectCommercialAuthorization.objects.filter(pk=replacement.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        with patch('api.routers.projects.ProjectEvent.objects.create', side_effect=IntegrityError):
            failed = self.api.post(
                f'/api/projects/{project.id}/start', headers=self.tokens['L3'],
                json=self.start_payload(replacement.json()['id']),
            )
        self.assertEqual(failed.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Planificado')
        self.assertEqual(ProjectEvent.objects.count(), 0)
        self.assertEqual(ProjectCommercialAuthorization.objects.count(), 2)

    @staticmethod
    def delivery_authorization_payload(scope, **overrides):
        payload = {
            'authorized_scope': scope,
            'effectivity_conditions': 'Condiciones comerciales y operativas de preparación cumplidas',
            'conditions_accredited': True,
            'evidence_reference': 'EXP-DELIVERY-22',
            'effective_at': (timezone.now() + timedelta(minutes=5)).isoformat(),
        }
        payload.update(overrides)
        return payload

    @staticmethod
    def technical_evaluation_payload(**overrides):
        payload = {
            'satisfactory': True,
            'technical_enablement_status': 'Vigente',
            'ordinary_close_valid': True,
            'obligations_compatible': True,
            'result_summary': 'El alcance integral vigente fue validado satisfactoriamente',
            'evidence': 'Informe técnico integral EXP-TEC-22',
            'ordinary_close_evidence': 'Cierre ordinario documentado',
            'obligations_assessment': 'Sin obligaciones incompatibles con la habilitación',
            'optional_task_assessments': [],
        }
        payload.update(overrides)
        return payload

    def create_validated_project(self, *, task_status='Finalizada', mandatory=True):
        project = Project.objects.create(
            client=self.client_record, name='Cierre integral', scope='Portal institucional y alcance acordado',
            status='En validación técnica',
        )
        self.coordinate_l3(project)
        l2 = Collaborator.objects.get(username='project-api-L2')
        l3 = Collaborator.objects.get(username='project-api-L3')
        l4 = Collaborator.objects.get(username='project-api-L4')
        l5 = Collaborator.objects.get(username='project-api-L5')
        validation_event = ProjectEvent.objects.create(
            event_type='ingreso_validacion_tecnica', project=project, actor=l3,
            previous_status='En ejecución', new_status='En validación técnica',
            reason='Validación iniciada', evidence='Preparación de validación acreditada',
        )
        task = Task.objects.create(
            project=project, title='Pruebas integrales', description='Validar el portal',
            status=task_status, created_by=l2, responsible=l4,
            assignee=l5 if task_status != 'Pendiente' else None,
            assigned_at=timezone.now() if task_status != 'Pendiente' else None,
        )
        if task_status == 'Finalizada':
            TaskEvent.objects.create(
                task=task, event_type='aprobada_revision', actor=l4,
                previous_status='En revisión', new_status='Finalizada',
                reason='Revisión satisfactoria',
            )
        classification = self.api.post(
            f'/api/projects/{project.id}/tasks/{task.id}/delivery-classification',
            headers=self.tokens['L3'], json={'is_mandatory': mandatory, 'reason': 'Clasificación según el alcance aprobado'},
        )
        self.assertEqual(classification.status_code, 200, classification.text)
        evaluation = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
            json=self.technical_evaluation_payload(),
        )
        return project, task, validation_event, evaluation

    def create_delivery_authorization(self, project, **overrides):
        return self.api.post(
            f'/api/projects/{project.id}/delivery-authorizations', headers=self.tokens['L2'],
            json=self.delivery_authorization_payload(project.scope, **overrides),
        )

    def test_l3_classifies_tasks_with_scope_and_preserves_each_revision(self):
        project = Project.objects.create(
            client=self.client_record, name='Clasificación con historial',
            scope='Alcance uno', status='En ejecución',
        )
        self.coordinate_l3(project)
        l2 = Collaborator.objects.get(username='project-api-L2')
        l4 = Collaborator.objects.get(username='project-api-L4')
        task = Task.objects.create(project=project, title='Tarea', created_by=l2, responsible=l4)
        first = self.api.post(
            f'/api/projects/{project.id}/tasks/{task.id}/delivery-classification', headers=self.tokens['L3'],
            json={'is_mandatory': False, 'reason': 'No es requisito del cierre ordinario'},
        )
        second = self.api.post(
            f'/api/projects/{project.id}/tasks/{task.id}/delivery-classification', headers=self.tokens['L3'],
            json={'is_mandatory': True, 'reason': 'Nueva decisión conforme al alcance aprobado'},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        revisions = list(ProjectTaskClassification.objects.filter(task=task).order_by('id'))
        self.assertEqual(len(revisions), 2)
        self.assertFalse(revisions[0].is_current)
        self.assertTrue(revisions[1].is_current)
        self.assertEqual(revisions[0].actor_id, Collaborator.objects.get(username='project-api-L3').id)
        self.assertEqual(revisions[0].scope_snapshot, 'Alcance uno')

    def test_task_classification_denies_non_l3_out_of_scope_and_inactive_coordination(self):
        project = Project.objects.create(
            client=self.client_record, name='Ámbito de clasificación', scope='Alcance', status='En ejecución',
        )
        l2 = Collaborator.objects.get(username='project-api-L2')
        l4 = Collaborator.objects.get(username='project-api-L4')
        task = Task.objects.create(project=project, title='Tarea', created_by=l2, responsible=l4)
        url = f'/api/projects/{project.id}/tasks/{task.id}/delivery-classification'
        for level in ('L1', 'L2', 'L4', 'L5'):
            self.assertEqual(self.api.post(
                url, headers=self.tokens[level], json={'is_mandatory': True, 'reason': 'Prueba'},
            ).status_code, 403)
        self.assertEqual(self.api.post(
            url, headers=self.tokens['L3'], json={'is_mandatory': True, 'reason': 'Prueba'},
        ).status_code, 404)
        self.coordinate_l3(project)
        ProjectCoordination.objects.filter(project=project).update(is_active=False)
        self.assertEqual(self.api.post(
            url, headers=self.tokens['L3'], json={'is_mandatory': True, 'reason': 'Prueba'},
        ).status_code, 404)
        self.assertEqual(ProjectTaskClassification.objects.count(), 0)

    def test_required_task_pending_blocks_ordinary_close_evaluation(self):
        project, _task, _validation_event, _initial = self.create_validated_project(
            task_status='Pendiente', mandatory=True,
        )
        response = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
            json=self.technical_evaluation_payload(),
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(ProjectTechnicalEvaluation.objects.filter(project=project).count(), 0)

    def test_optional_pending_task_requires_individual_l3_assessment(self):
        project, task, _validation_event, _initial = self.create_validated_project(
            task_status='Pendiente', mandatory=False,
        )
        missing = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
            json=self.technical_evaluation_payload(),
        )
        self.assertEqual(missing.status_code, 409, missing.text)
        payload = self.technical_evaluation_payload(optional_task_assessments=[{
            'task_id': task.id, 'impact_assessment': 'No impide la entrega preparada',
            'evidence': 'Evaluación L3 de impacto EXP-22',
        }])
        accepted = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'], json=payload,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)

    def test_ready_transition_requires_current_evaluation_and_delivery_authorization(self):
        project, _task, validation_event, evaluation = self.create_validated_project()
        self.assertEqual(evaluation.status_code, 200, evaluation.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')
        auth = self.create_delivery_authorization(project)
        self.assertEqual(auth.status_code, 201, auth.text)
        authorization = ProjectDeliveryAuthorization.objects.get(pk=auth.json()['id'])
        now = timezone.now()
        ProjectDeliveryAuthorization.objects.filter(pk=authorization.pk).update(effective_at=now - timedelta(seconds=1))
        response = self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': authorization.id, 'reason': 'Cierre ordinario validado'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        project.refresh_from_db()
        self.assertEqual(project.status, 'Listo para entrega')
        transition = ProjectEvent.objects.get(project=project, event_type='listo_para_entrega')
        self.assertEqual(transition.previous_status, 'En validación técnica')
        self.assertEqual(transition.new_status, 'Listo para entrega')
        self.assertEqual(transition.technical_evaluation_id, evaluation.json()['id'])
        self.assertEqual(transition.delivery_authorization_id, authorization.id)
        self.assertEqual(transition.actor_id, Collaborator.objects.get(username='project-api-L3').id)
        self.assertEqual(transition.technical_evaluation.validation_event_id, validation_event.id)

    def test_unsatisfactory_or_unsubstantiated_technical_evaluation_cannot_enable_ready(self):
        project, _task, _validation_event, _initial = self.create_validated_project()
        blank_evidence = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
            json=self.technical_evaluation_payload(evidence='   '),
        )
        self.assertEqual(blank_evidence.status_code, 422, blank_evidence.text)
        unsatisfactory = self.api.post(
            f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
            json=self.technical_evaluation_payload(
                satisfactory=False, ordinary_close_valid=False,
                technical_enablement_status='En revisión',
            ),
        )
        self.assertEqual(unsatisfactory.status_code, 200, unsatisfactory.text)
        authorization = self.create_delivery_authorization(project)
        self.assertEqual(authorization.status_code, 201, authorization.text)
        ProjectDeliveryAuthorization.objects.filter(pk=authorization.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        response = self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': authorization.json()['id'], 'reason': 'Cierre'},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')

    def test_ready_transition_rejects_scope_changes_after_evaluation(self):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        authorization = self.create_delivery_authorization(project)
        self.assertEqual(authorization.status_code, 201, authorization.text)
        ProjectDeliveryAuthorization.objects.filter(pk=authorization.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        Project.objects.filter(pk=project.pk).update(scope='Alcance actual modificado')
        response = self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': authorization.json()['id'], 'reason': 'Cierre'},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')

    def test_ready_transition_rejects_non_l3_wrong_scope_and_wrong_origin_without_writes(self):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        auth = self.create_delivery_authorization(project)
        self.assertEqual(auth.status_code, 201, auth.text)
        for level in ('L1', 'L2', 'L4', 'L5'):
            self.assertEqual(self.api.post(
                f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens[level],
                json={'delivery_authorization_id': auth.json()['id'], 'reason': 'Cierre'},
            ).status_code, 403)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': 999999, 'reason': 'Cierre'},
        ).status_code, 409)
        ProjectCoordination.objects.filter(project=project).update(is_active=False)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': auth.json()['id'], 'reason': 'Cierre'},
        ).status_code, 404)
        self.assertFalse(ProjectEvent.objects.filter(project=project, event_type='listo_para_entrega').exists())
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')

    def test_ready_rejects_foreign_future_withdrawn_replaced_and_expired_authorizations(self):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        foreign_project = Project.objects.create(
            client=self.client_record, name='Otro proyecto', scope=project.scope,
        )
        foreign = self.create_delivery_authorization(foreign_project)
        self.assertEqual(foreign.status_code, 201, foreign.text)
        valid = self.create_delivery_authorization(project)
        self.assertEqual(valid.status_code, 201, valid.text)
        ProjectDeliveryAuthorization.objects.filter(pk=foreign.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        payload = {'delivery_authorization_id': valid.json()['id'], 'reason': 'Cierre'}
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': foreign.json()['id'], 'reason': 'Cierre'},
        ).status_code, 409)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'], json=payload,
        ).status_code, 409)  # Aún no efectiva.
        auth_id = valid.json()['id']
        ProjectDeliveryAuthorization.objects.filter(pk=auth_id).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/delivery-authorizations/{auth_id}/withdrawal',
            headers=self.tokens['L2'], json={'reason': 'Condición comercial retirada'},
        ).status_code, 200)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'], json=payload,
        ).status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')

        replaced_project, _task, _validation_event, _evaluation = self.create_validated_project()
        original = self.create_delivery_authorization(replaced_project)
        replacement = self.create_delivery_authorization(
            replaced_project, replaces_authorization_id=original.json()['id'],
            replacement_reason='La habilitación se sustituyó por una nueva decisión L2',
        )
        ProjectDeliveryAuthorization.objects.filter(pk=replacement.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        old_response = self.api.post(
            f'/api/projects/{replaced_project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': original.json()['id'], 'reason': 'Cierre'},
        )
        new_response = self.api.post(
            f'/api/projects/{replaced_project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': replacement.json()['id'], 'reason': 'Cierre'},
        )
        self.assertEqual(old_response.status_code, 409, old_response.text)
        self.assertEqual(new_response.status_code, 200, new_response.text)

        expired_project, _task, _validation_event, _evaluation = self.create_validated_project()
        expired = self.create_delivery_authorization(
            expired_project,
            effective_at=(timezone.now() + timedelta(minutes=4)).isoformat(),
            expires_at=(timezone.now() + timedelta(minutes=6)).isoformat(),
        )
        ProjectDeliveryAuthorization.objects.filter(pk=expired.json()['id']).update(
            effective_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() - timedelta(days=1),
        )
        expired_response = self.api.post(
            f'/api/projects/{expired_project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': expired.json()['id'], 'reason': 'Cierre'},
        )
        self.assertEqual(expired_response.status_code, 409, expired_response.text)

    def test_delivery_authorization_requires_l2_effective_conditions_and_matching_scope(self):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        for level in ('L1', 'L3', 'L4', 'L5'):
            response = self.api.post(
                f'/api/projects/{project.id}/delivery-authorizations', headers=self.tokens[level],
                json=self.delivery_authorization_payload(project.scope),
            )
            self.assertEqual(response.status_code, 403)
        missing_conditions = self.create_delivery_authorization(project, conditions_accredited=False)
        mismatch = self.create_delivery_authorization(project, authorized_scope='Otro alcance')
        self.assertEqual(missing_conditions.status_code, 409)
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(ProjectDeliveryAuthorization.objects.filter(project=project).count(), 0)

    def test_replaced_delivery_authorization_preserves_history(self):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        original = self.create_delivery_authorization(project)
        self.assertEqual(original.status_code, 201, original.text)
        replacement = self.create_delivery_authorization(
            project, replaces_authorization_id=original.json()['id'], replacement_reason='Se actualizó la autorización',
        )
        self.assertEqual(replacement.status_code, 201, replacement.text)
        prior = ProjectDeliveryAuthorizationEvent.objects.get(authorization_id=original.json()['id'])
        self.assertEqual(prior.event_type, 'sustituida')
        self.assertEqual(prior.replacement_id, replacement.json()['id'])
        self.assertEqual(ProjectDeliveryAuthorization.objects.filter(project=project).count(), 2)

    def test_technical_evaluation_invalidates_after_task_or_scope_changes(self):
        project, task, _validation_event, evaluation = self.create_validated_project()
        self.assertEqual(evaluation.status_code, 200, evaluation.text)
        auth = self.create_delivery_authorization(project)
        self.assertEqual(auth.status_code, 201, auth.text)
        TaskEvent.objects.create(
            task=task, event_type='reapertura_autorizada', actor=Collaborator.objects.get(username='project-api-L3'),
            previous_status='Finalizada', new_status='Observada', reason='Reapertura de prueba',
        )
        task.status = 'Observada'
        task.save(update_fields=['status'])
        response = self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': auth.json()['id'], 'reason': 'Cierre'},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')

    def test_ready_transition_rolls_back_project_and_event_together(self):
        project, _task, _validation_event, evaluation = self.create_validated_project()
        auth = self.create_delivery_authorization(project)
        self.assertEqual(auth.status_code, 201, auth.text)
        ProjectDeliveryAuthorization.objects.filter(pk=auth.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=1),
        )
        with patch('api.routers.projects.ProjectEvent.objects.create', side_effect=IntegrityError):
            response = self.api.post(
                f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
                json={'delivery_authorization_id': auth.json()['id'], 'reason': 'Cierre'},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'En validación técnica')
        self.assertFalse(ProjectEvent.objects.filter(project=project, event_type='listo_para_entrega').exists())
        self.assertTrue(ProjectTechnicalEvaluation.objects.filter(project=project).exists())

    def prepare_delivery_project(self, *, validated_versions=None):
        project, _task, _validation_event, _evaluation = self.create_validated_project()
        if validated_versions:
            evaluated = self.api.post(
                f'/api/projects/{project.id}/technical-evaluations', headers=self.tokens['L3'],
                json=self.technical_evaluation_payload(validated_versions=validated_versions),
            )
            self.assertEqual(evaluated.status_code, 200, evaluated.text)
        authorization = self.create_delivery_authorization(project)
        self.assertEqual(authorization.status_code, 201, authorization.text)
        ProjectDeliveryAuthorization.objects.filter(pk=authorization.json()['id']).update(
            effective_at=timezone.now() - timedelta(seconds=2),
        )
        ready = self.api.post(
            f'/api/projects/{project.id}/ready-for-delivery', headers=self.tokens['L3'],
            json={'delivery_authorization_id': authorization.json()['id'], 'reason': 'Cierre técnico ordinario'},
        )
        self.assertEqual(ready.status_code, 200, ready.text)
        return project, authorization.json()['id']

    @staticmethod
    def project_delivery_payload(authorization_id, **overrides):
        payload = {
            'delivery_type': 'integral', 'preparation_authorization_id': authorization_id,
            'scope': 'Portal institucional y alcance acordado',
            'scope_within_authorization': True, 'covers_project_scope': True,
            'version_reference': 'release-1.0', 'recipient': 'Responsable del cliente',
            'delivery_method': 'Transferencia en repositorio acordado', 'performed_by': 'Equipo autorizado',
            'evidence_reference': 'EXP-TRANSFERENCIA-01', 'occurred_at': timezone.now().isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_l2_records_and_formalizes_integral_delivery_atomically(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        delivery_response = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json=self.project_delivery_payload(authorization_id),
        )
        self.assertEqual(delivery_response.status_code, 201, delivery_response.text)
        delivery = ProjectDelivery.objects.get(pk=delivery_response.json()['id'])
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Listo para entrega')
        self.assertTrue(delivery.scope_within_authorization)
        formalized = self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'],
            json={'delivery_ids': [delivery.id], 'integral_coverage_confirmed': True,
                  'coverage_evidence': 'La transferencia cubre el alcance actual', 'reason': 'Entrega formal ordinaria'},
        )
        self.assertEqual(formalized.status_code, 200, formalized.text)
        project.refresh_from_db()
        self.assertEqual(project.status, 'Entregado')
        event = ProjectEvent.objects.get(project=project, event_type='entrega_formalizada')
        self.assertEqual((event.previous_status, event.new_status), ('Listo para entrega', 'Entregado'))
        self.assertEqual(event.actor.username, 'project-api-L2')
        self.assertEqual(list(event.delivery_records.values_list('id', flat=True)), [delivery.id])
        self.assertIn('EXP-TRANSFERENCIA-01', event.evidence)
        self.assertIn('fecha efectiva=', event.evidence)
        self.assertFalse(ProjectEvent.objects.filter(project=project, new_status__icontains='acept').exists())

    def test_delivery_rejects_wrong_role_origin_and_missing_transfer_evidence_without_writes(self):
        project, authorization_id = self.prepare_delivery_project()
        payload = self.project_delivery_payload(authorization_id)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L3'], json=payload,
        ).status_code, 403)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json={**payload, 'evidence_reference': '   '},
        ).status_code, 422)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json={**payload, 'scope_within_authorization': False},
        ).status_code, 422)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/delivery-version-reviews', headers=self.tokens['L2'],
            json={'version_reference': 'release-1', 'satisfactory': True, 'technical_enablement_status': 'Vigente',
                  'result_summary': 'Revisión', 'evidence': 'EXP-REV'},
        ).status_code, 403)
        ProjectCoordination.objects.filter(project=project).update(is_active=False)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/delivery-version-reviews', headers=self.tokens['L3'],
            json={'version_reference': 'release-1', 'satisfactory': True, 'technical_enablement_status': 'Vigente',
                  'result_summary': 'Revisión', 'evidence': 'EXP-REV'},
        ).status_code, 404)
        self.assertEqual(self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L3'],
            json={'delivery_ids': [1], 'integral_coverage_confirmed': True,
                  'coverage_evidence': 'Cobertura', 'reason': 'Entrega'},
        ).status_code, 403)
        Project.objects.filter(pk=project.id).update(status='En ejecución')
        failed = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'], json=payload,
        )
        self.assertEqual(failed.status_code, 409, failed.text)
        self.assertEqual(ProjectDelivery.objects.filter(project=project).count(), 0)
        self.assertFalse(ProjectEvent.objects.filter(project=project, event_type='entrega_formalizada').exists())

    def test_expired_authorization_and_pre_ready_transfer_cannot_be_formalized(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        payload = self.project_delivery_payload(authorization_id)
        expired_at = timezone.now() - timedelta(seconds=1)
        ProjectDeliveryAuthorization.objects.filter(pk=authorization_id).update(expires_at=expired_at)
        rejected = self.api.post(f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'], json=payload)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        ProjectDeliveryAuthorization.objects.filter(pk=authorization_id).update(expires_at=None)
        ready_event = ProjectEvent.objects.get(project=project, event_type='listo_para_entrega')
        ProjectDeliveryAuthorization.objects.filter(pk=authorization_id).update(
            authorized_at=ready_event.occurred_at - timedelta(hours=1),
            effective_at=ready_event.occurred_at - timedelta(hours=1),
        )
        payload['occurred_at'] = (ready_event.occurred_at - timedelta(minutes=1)).isoformat()
        recorded = self.api.post(f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'], json=payload)
        self.assertEqual(recorded.status_code, 201, recorded.text)
        formalized = self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'],
            json={'delivery_ids': [recorded.json()['id']], 'integral_coverage_confirmed': True,
                  'coverage_evidence': 'Cobertura documentada', 'reason': 'Entrega ordinaria'},
        )
        self.assertEqual(formalized.status_code, 409, formalized.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Listo para entrega')
        self.assertFalse(ProjectDeliveryTransition.objects.filter(delivery_id=recorded.json()['id']).exists())

    def test_unvalidated_version_requires_current_satisfactory_l3_review(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        review = self.api.post(
            f'/api/projects/{project.id}/delivery-version-reviews', headers=self.tokens['L3'],
            json={'version_reference': 'release-2.0', 'satisfactory': True,
                  'technical_enablement_status': 'Vigente', 'result_summary': 'Versión revisada antes de transferir',
                  'evidence': 'EXP-TEC-V2'},
        )
        self.assertEqual(review.status_code, 200, review.text)
        delivery = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json=self.project_delivery_payload(authorization_id, version_reference='release-2.0'),
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        formalize_payload = {'delivery_ids': [delivery.json()['id']], 'integral_coverage_confirmed': True,
                             'coverage_evidence': 'Cobertura integral', 'reason': 'Entrega'}
        accepted = self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'], json=formalize_payload,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(ProjectDeliveryTechnicalReview.objects.count(), 1)

    def test_review_after_transfer_does_not_retroactively_enable_delivered_version(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        delivery = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json=self.project_delivery_payload(authorization_id, version_reference='release-2.0'),
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        review = self.api.post(
            f'/api/projects/{project.id}/delivery-version-reviews', headers=self.tokens['L3'],
            json={'version_reference': 'release-2.0', 'satisfactory': True,
                  'technical_enablement_status': 'Vigente', 'result_summary': 'Revisión posterior',
                  'evidence': 'EXP-TEC-V2'},
        )
        self.assertEqual(review.status_code, 200, review.text)
        rejected = self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'],
            json={'delivery_ids': [delivery.json()['id']], 'integral_coverage_confirmed': True,
                  'coverage_evidence': 'Cobertura integral', 'reason': 'Entrega'},
        )
        self.assertEqual(rejected.status_code, 409, rejected.text)

    def test_changed_tasks_after_ready_require_a_new_technical_close_before_delivery(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        task = Task.objects.get(project=project)
        Task.objects.filter(pk=task.pk).update(status='Observada')
        delivery = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json=self.project_delivery_payload(authorization_id),
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        rejected = self.api.post(
            f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'],
            json={'delivery_ids': [delivery.json()['id']], 'integral_coverage_confirmed': True,
                  'coverage_evidence': 'Cobertura integral', 'reason': 'Entrega'},
        )
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Listo para entrega')

    def test_delivery_formalization_rolls_back_state_event_and_delivery_link(self):
        project, authorization_id = self.prepare_delivery_project(validated_versions=['release-1.0'])
        delivery = self.api.post(
            f'/api/projects/{project.id}/deliveries', headers=self.tokens['L2'],
            json=self.project_delivery_payload(authorization_id),
        )
        self.assertEqual(delivery.status_code, 201, delivery.text)
        payload = {'delivery_ids': [delivery.json()['id']], 'integral_coverage_confirmed': True,
                   'coverage_evidence': 'Cobertura integral', 'reason': 'Entrega'}
        with patch('api.routers.projects.ProjectDeliveryTransition.objects.bulk_create', side_effect=IntegrityError):
            failed = self.api.post(
                f'/api/projects/{project.id}/deliveries/formalize', headers=self.tokens['L2'], json=payload,
            )
        self.assertEqual(failed.status_code, 409)
        self.assertEqual(Project.objects.get(pk=project.id).status, 'Listo para entrega')
        self.assertFalse(ProjectEvent.objects.filter(project=project, event_type='entrega_formalizada').exists())
        self.assertFalse(ProjectDeliveryTransition.objects.filter(delivery_id=delivery.json()['id']).exists())

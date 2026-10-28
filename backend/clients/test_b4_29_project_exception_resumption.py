from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.dependencies import require_route_permission
from api.routers import auth, projects, tasks
from api.routers.projects import ensure_project_not_cancelled
from api.routers.tasks import lock_project_for_task_action
from api.routers.auth import hash_password
from clients.models import (
    Client, Collaborator, Project, ProjectCancellation, ProjectCancellationEvent,
    OrganizationalSubstitution, ProjectCoordination, ProjectEvent, ProjectResumptionEvent,
    Role, Task, WebCatalog,
)

test_api = FastAPI()
test_api.include_router(auth.router, prefix='/api/auth')
test_api.include_router(
    projects.router, prefix='/api/projects', dependencies=[Depends(require_route_permission)],
)
test_api.include_router(
    tasks.router, prefix='/api/tasks', dependencies=[Depends(require_route_permission)],
)

class ProjectExceptionAndResumptionApiTests(TransactionTestCase):
    def setUp(self):
        self.actors = {}
        self.tokens = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'B4-29 {level}', level=level)
            person = Collaborator.objects.create(
                first_name='B429', last_name=level, document_number=f'B429-{level}',
                email=f'b429-{level}@example.com', username=f'b429-{level}',
                password_hash=hash_password('test-password'), role=role,
            )
            self.actors[level] = person
        catalog = WebCatalog.objects.create(name='B4-29 test', base_price_rent=1, base_price_sale=2)
        client_record = Client.objects.create(
            name='B4-29 cliente', document_type='DNI', document_number='B429-CLIENT',
            web_type=catalog, plan='alquiler',
        )
        self.project = Project.objects.create(client=client_record, name='B4-29 proyecto', scope='Alcance')
        self.coordination = ProjectCoordination.objects.create(
            project=self.project, coordinator=self.actors['L3'], assigned_by=self.actors['L2'],
        )
        self.api = TestClient(test_api)
        for level in self.actors:
            response = self.api.post('/api/auth/login', json={
                'username': f'b429-{level}', 'password': 'test-password',
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.tokens[level] = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def cancellation(self, *, exceptional=False):
        item = ProjectCancellation.objects.create(
            project=self.project, opened_by=self.actors['L2'], cancelled_scope='Alcance',
            reason='Cierre solicitado', evidence='Documento de solicitud',
        )
        if exceptional:
            ProjectCancellationEvent.objects.create(
                cancellation=item, event_type='evaluacion_tecnica', actor=self.actors['L3'],
                reason='Excepción técnica', evidence='Informe técnico',
                data={'l1_intervention_required': True, 'l1_exception_reason': 'Riesgo excepcional'},
            )
            ProjectCancellationEvent.objects.create(
                cancellation=item, event_type='escalamiento_l1', actor=self.actors['L2'],
                reason='Fuera de competencia', evidence='Evaluación comercial',
                data={
                    'source': 'evaluacion_comercial_l2', 'within_l2_competence': False,
                    'commercial_consequences': 'Consecuencias excepcionales',
                    'effectivity_conditions': 'Condiciones registradas',
                },
            )
            planned = timezone.now() + timedelta(minutes=5)
            ProjectCancellationEvent.objects.create(
                cancellation=item, event_type='decision_l1_autorizada', actor=self.actors['L1'],
                reason='Autorización excepcional', evidence='Resolución L1',
                data={
                    'authority': 'L1 exceptional cancellation',
                    'planned_effective_at': planned.isoformat(),
                    'preserves_restriction_until_resumption': True,
                },
            )
            return item, planned
        ProjectCancellationEvent.objects.create(
            cancellation=item, event_type='solicitada', actor=self.actors['L2'],
            reason='Cierre solicitado', evidence='Documento de solicitud', data={},
        )
        return item, None

    def make_effective(self, cancellation, planned=None):
        effective_at = timezone.now()
        ProjectCancellationEvent.objects.create(
            cancellation=cancellation, event_type='efectiva', actor=self.actors['L2'],
            reason='Cancelación efectiva', evidence='Constancia', effective_at=effective_at,
            data={'conditions_satisfied': True},
        )
        return effective_at

    def test_l1_exception_decision_and_l2_effectivity_keep_distinct_authorities(self):
        cancellation, planned = self.cancellation(exceptional=True)
        # This case is already resolved by L1; L2 only records effectivity after its date.
        response = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/effectivity',
            headers=self.tokens['L2'], json={'conditions_satisfied': True, 'reason': 'Condiciones cumplidas', 'evidence': 'Acta'},
        )
        self.assertEqual(response.status_code, 409, response.text)
        with patch('api.routers.projects.timezone.now', return_value=planned + timedelta(seconds=1)):
            response = self.api.post(
                f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/effectivity',
                headers=self.tokens['L2'], json={'conditions_satisfied': True, 'reason': 'Condiciones cumplidas', 'evidence': 'Acta'},
            )
        self.assertEqual(response.status_code, 200, response.text)
        cancellation.refresh_from_db()
        event_types = list(cancellation.events.values_list('event_type', flat=True))
        self.assertIn('decision_l1_autorizada', event_types)
        self.assertIn('efectiva', event_types)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'Planificado')

    def test_l1_authorizes_only_a_formally_accredited_exception(self):
        opened = self.api.post(
            f'/api/projects/{self.project.id}/cancellations', headers=self.tokens['L2'],
            json={'cancelled_scope': 'Alcance', 'reason': 'Solicitud', 'evidence': 'Solicitud firmada'},
        )
        self.assertEqual(opened.status_code, 201, opened.text)
        cancellation_id = opened.json()['id']
        technical = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Trabajo afectado registrado',
                'obligations_assessment': 'Obligaciones registradas',
                'evidence': 'Informe L3', 'l1_intervention_required': True,
                'l1_exception_reason': 'Riesgo técnico fuera del tratamiento ordinario',
            },
        )
        self.assertEqual(technical.status_code, 200, technical.text)
        commercial = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/commercial-evaluation',
            headers=self.tokens['L2'], json={
                'within_l2_competence': False,
                'commercial_consequences': 'Consecuencia fuera de competencia L2',
                'effectivity_conditions': 'Condiciones pendientes documentadas',
                'evidence': 'Evaluación comercial L2',
            },
        )
        self.assertEqual(commercial.status_code, 200, commercial.text)
        planned = timezone.now() + timedelta(minutes=5)
        decision = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/exceptional-decision',
            headers=self.tokens['L1'], json={
                'authorized': True, 'reason': 'Resolución excepcional',
                'evidence': 'Resolución L1', 'planned_effective_at': planned.isoformat(),
            },
        )
        self.assertEqual(decision.status_code, 200, decision.text)
        l1_event = next(item for item in decision.json()['events'] if item['event_type'] == 'decision_l1_autorizada')
        self.assertEqual(l1_event['actor_id'], self.actors['L1'].id)
        self.assertEqual(l1_event['data']['commercial_consequences'], 'Consecuencia fuera de competencia L2')

    def test_l1_denial_closes_exception_case_without_project_effects(self):
        opened = self.api.post(
            f'/api/projects/{self.project.id}/cancellations', headers=self.tokens['L2'],
            json={'cancelled_scope': 'Alcance', 'reason': 'Solicitud', 'evidence': 'Solicitud firmada'},
        )
        cancellation_id = opened.json()['id']
        self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/technical-evaluation',
            headers=self.tokens['L3'], json={
                'affected_tasks_assessment': 'Impacto evaluado', 'obligations_assessment': 'Obligaciones evaluadas',
                'evidence': 'Informe técnico', 'l1_intervention_required': True,
                'l1_exception_reason': 'Excepción documentada',
            },
        )
        self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/commercial-evaluation',
            headers=self.tokens['L2'], json={
                'within_l2_competence': True, 'commercial_consequences': 'Evaluadas',
                'effectivity_conditions': 'Condiciones', 'evidence': 'Evidencia comercial',
            },
        )
        denied = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation_id}/exceptional-decision',
            headers=self.tokens['L1'], json={
                'authorized': False, 'reason': 'No se autoriza', 'evidence': 'Denegación L1',
            },
        )
        self.assertEqual(denied.status_code, 200, denied.text)
        self.assertEqual(denied.json()['events'][-1]['event_type'], 'decision_l1_denegada')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'Planificado')
        lock_project_for_task_action(self.project.id)

    def test_l2_cannot_resolve_a_case_with_accredited_l1_exception(self):
        cancellation, _planned = self.cancellation(exceptional=True)
        before = cancellation.events.count()
        response = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/decision',
            headers=self.tokens['L2'], json={
                'authorized': False, 'reason': 'Denegación L2', 'evidence': 'Registro',
            },
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(cancellation.events.count(), before)

    def test_l1_decision_rejects_unaccredited_exception_without_partial_writes(self):
        cancellation, _planned = self.cancellation(exceptional=False)
        before = ProjectEvent.objects.count()
        response = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/exceptional-decision',
            headers=self.tokens['L1'], json={
                'authorized': False, 'reason': 'Decisión', 'evidence': 'Evidencia',
            },
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(cancellation.events.count(), 1)
        self.assertEqual(ProjectEvent.objects.count(), before)

    def test_l2_cannot_call_exceptional_decision_endpoint(self):
        cancellation, _planned = self.cancellation(exceptional=True)
        response = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/exceptional-decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Decisión', 'evidence': 'Evidencia',
                'planned_effective_at': (timezone.now() + timedelta(minutes=2)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_ordinary_resumption_records_a_separate_fact_and_preserves_tasks(self):
        cancellation, _planned = self.cancellation()
        self.make_effective(cancellation)
        task = Task.objects.create(
            project=self.project, title='Pendiente histórico', status='Cancelada',
            created_by=self.actors['L3'], responsible=self.actors['L4'],
        )
        evaluated = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/resumption/technical-evaluation',
            headers=self.tokens['L3'], json={
                'feasibility': 'Viable bajo el alcance vigente',
                'pending_work': 'Trabajo pendiente conservado', 'evidence': 'Informe L3',
            },
        )
        self.assertEqual(evaluated.status_code, 201, evaluated.text)
        resumption_id = evaluated.json()['id']
        decided = self.api.post(
            f'/api/projects/resumptions/{resumption_id}/commercial-decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Condiciones aceptadas',
                'conditions': 'Condiciones registradas', 'evidence': 'Acta L2',
            },
        )
        self.assertEqual(decided.status_code, 200, decided.text)
        self.assertIn('reanudacion_registrada', [item['event_type'] for item in decided.json()['events']])
        self.project.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(self.project.status, 'Planificado')
        self.assertEqual(task.status, 'Cancelada')
        ensure_project_not_cancelled(self.project.id)
        lock_project_for_task_action(self.project.id)

    def test_resumption_cannot_apply_to_an_older_cancellation(self):
        cancellation, _planned = self.cancellation()
        ProjectCancellationEvent.objects.create(
            cancellation=cancellation, event_type='efectiva', actor=self.actors['L2'],
            reason='Cancelación efectiva anterior', evidence='Constancia anterior',
            effective_at=timezone.now() - timedelta(minutes=2), data={'conditions_satisfied': True},
        )
        newer = ProjectCancellation.objects.create(
            project=self.project, opened_by=self.actors['L2'], cancelled_scope='Alcance',
            reason='Nueva cancelación', evidence='Nueva evidencia',
        )
        ProjectCancellationEvent.objects.create(
            cancellation=newer, event_type='efectiva', actor=self.actors['L2'],
            reason='Nueva cancelación efectiva', evidence='Constancia posterior',
            effective_at=timezone.now() - timedelta(minutes=1), data={'conditions_satisfied': True},
        )
        before = ProjectResumptionEvent.objects.count()
        response = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/resumption/technical-evaluation',
            headers=self.tokens['L3'], json={
                'feasibility': 'Viable', 'pending_work': 'Pendientes', 'evidence': 'Informe L3',
            },
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(ProjectResumptionEvent.objects.count(), before)
        self.assertFalse(self.project.resumptions.exists())

    def test_exceptional_resumption_waits_for_l1_and_does_not_restore_project_or_tasks(self):
        cancellation, _planned = self.cancellation(exceptional=True)
        self.make_effective(cancellation)
        evaluated = self.api.post(
            f'/api/projects/{self.project.id}/cancellations/{cancellation.id}/resumption/technical-evaluation',
            headers=self.tokens['L3'], json={
                'feasibility': 'Viable', 'pending_work': 'Pendientes existentes', 'evidence': 'Informe L3',
            },
        )
        self.assertEqual(evaluated.status_code, 201, evaluated.text)
        resumption_id = evaluated.json()['id']
        commercial = self.api.post(
            f'/api/projects/resumptions/{resumption_id}/commercial-decision',
            headers=self.tokens['L2'], json={
                'authorized': True, 'reason': 'Condiciones registradas',
                'conditions': 'Viable comercialmente', 'evidence': 'Acta L2',
            },
        )
        self.assertEqual(commercial.status_code, 200, commercial.text)
        self.assertNotIn('reanudacion_registrada', [item['event_type'] for item in commercial.json()['events']])
        resumed = self.api.post(
            f'/api/projects/resumptions/{resumption_id}/exceptional-decision',
            headers=self.tokens['L1'], json={
                'authorized': True, 'reason': 'Restricción levantada para reanudar',
                'conditions': 'Condiciones L1', 'evidence': 'Resolución L1',
            },
        )
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertIn('reanudacion_registrada', [item['event_type'] for item in resumed.json()['events']])
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'Planificado')
        ensure_project_not_cancelled(self.project.id)
        lock_project_for_task_action(self.project.id)

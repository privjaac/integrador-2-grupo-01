from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.dependencies import require_route_permission
from api.routers import auth, projects, tasks
from api.routers.auth import hash_password
from clients.models import (
    Client, Collaborator, OrganizationalSubstitution, Project, ProjectCoordination,
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

class ProjectSubstitutionApiTests(TransactionTestCase):
    def setUp(self):
        self.actors = {}
        self.tokens = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'B4-28 {level}', level=level)
            person = Collaborator.objects.create(
                first_name='B428', last_name=level, document_number=f'B428-{level}',
                email=f'b428-{level}@example.com', username=f'b428-{level}',
                password_hash=hash_password('test-password'), role=role,
            )
            self.actors[level] = person
        catalog = WebCatalog.objects.create(name='B4-28 test', base_price_rent=1, base_price_sale=2)
        client_record = Client.objects.create(
            name='B4-28 cliente', document_type='DNI', document_number='B428-CLIENT',
            web_type=catalog, plan='alquiler',
        )
        self.project = Project.objects.create(client=client_record, name='B4-28 proyecto', scope='Alcance')
        self.coordination = ProjectCoordination.objects.create(
            project=self.project, coordinator=self.actors['L3'], assigned_by=self.actors['L2'],
        )
        self.api = TestClient(test_api)
        for level in self.actors:
            response = self.api.post('/api/auth/login', json={
                'username': f'b428-{level}', 'password': 'test-password',
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

    def test_l4_substitution_is_scoped_time_limited_and_can_review_only(self):
        from clients.models import ProjectLeadership, TeamMembership
        substitute = Collaborator.objects.create(
            first_name='B429', last_name='L4 substitute', document_number='B429-L4-SUB',
            email='b429-l4-sub@example.com', username='b429-l4-sub',
            password_hash=hash_password('test-password'), role=self.actors['L4'].role,
        )
        leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.actors['L4'], designated_by=self.actors['L3'],
        )
        TeamMembership.objects.create(
            leadership=leadership, developer=self.actors['L5'], added_by=self.actors['L4'],
        )
        task = Task.objects.create(
            project=self.project, title='Revisión acotada', status='En revisión',
            created_by=self.actors['L3'], responsible=self.actors['L4'], assignee=self.actors['L5'],
            assigned_at=timezone.now(),
        )
        self.actors['L4'].is_active = False
        self.actors['L4'].save(update_fields=['is_active'])
        login = self.api.post('/api/auth/login', json={
            'username': 'b429-l4-sub', 'password': 'test-password',
        })
        substitute_headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
        started = timezone.now() - timedelta(minutes=1)
        ends = timezone.now() + timedelta(minutes=10)
        appointed = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L3'], json={
                'coordination_id': self.coordination.id, 'leadership_id': leadership.id,
                'absent_level': 'L4', 'absent_person_id': self.actors['L4'].id,
                'substitute_id': substitute.id, 'reason': 'Ausencia registrada',
                'evidence': 'Constancia de ausencia', 'scope': 'Equipo de este proyecto',
                'faculties': ['tasks.view', 'tasks.review'],
                'valid_from': started.isoformat(), 'valid_until': ends.isoformat(),
            },
        )
        self.assertEqual(appointed.status_code, 201, appointed.text)
        visible = self.api.get(f'/api/tasks/{task.id}', headers=substitute_headers)
        self.assertEqual(visible.status_code, 200, visible.text)
        self.assertTrue(visible.json()['actions']['can_review'])
        reviewed = self.api.post(
            f'/api/tasks/{task.id}/review', headers=substitute_headers,
            json={'resolution': 'Finalizada', 'reason': 'Revisión completada'},
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        task.refresh_from_db()
        self.assertEqual(task.status, 'Finalizada')
        ended = self.api.post(
            f'/api/projects/{self.project.id}/substitutions/{appointed.json()["id"]}/end',
            headers=self.tokens['L3'],
        )
        self.assertEqual(ended.status_code, 200, ended.text)
        denied = self.api.get(f'/api/tasks/{task.id}', headers=substitute_headers)
        self.assertEqual(denied.status_code, 404, denied.text)

    def test_l4_substitution_rejects_out_of_scope_and_unsupported_faculties(self):
        from clients.models import ProjectLeadership
        substitute = Collaborator.objects.create(
            first_name='B429', last_name='Otro L4', document_number='B429-L4-OTHER',
            email='b429-l4-other@example.com', username='b429-l4-other',
            password_hash=hash_password('test-password'), role=self.actors['L4'].role,
        )
        leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.actors['L4'], designated_by=self.actors['L3'],
        )
        started = timezone.now() - timedelta(minutes=1)
        ends = timezone.now() + timedelta(minutes=10)
        payload = {
            'coordination_id': self.coordination.id, 'leadership_id': leadership.id,
            'absent_level': 'L4', 'absent_person_id': self.actors['L4'].id,
            'substitute_id': substitute.id, 'reason': 'Ausencia',
            'evidence': 'Constancia', 'scope': 'Proyecto',
            'faculties': ['tasks.view', 'tasks.assign'],
            'valid_from': started.isoformat(), 'valid_until': ends.isoformat(),
        }
        response = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L3'], json=payload,
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.project.coordinations.get().substitutions.count(), 0)

    def test_expired_substitution_is_closed_and_does_not_block_a_new_appointment(self):
        from clients.models import ProjectLeadership
        leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.actors['L4'], designated_by=self.actors['L3'],
        )
        substitute = Collaborator.objects.create(
            first_name='B429', last_name='L4 temporal', document_number='B429-L4-TEMP',
            email='b429-l4-temp@example.com', username='b429-l4-temp',
            password_hash=hash_password('test-password'), role=self.actors['L4'].role,
        )
        now = timezone.now()
        payload = {
            'coordination_id': self.coordination.id, 'leadership_id': leadership.id,
            'absent_level': 'L4', 'absent_person_id': self.actors['L4'].id,
            'substitute_id': substitute.id, 'reason': 'Ausencia documentada',
            'evidence': 'Constancia', 'scope': 'Equipo del proyecto',
            'faculties': ['tasks.view', 'tasks.review'],
            'valid_from': (now - timedelta(minutes=5)).isoformat(),
            'valid_until': (now - timedelta(minutes=1)).isoformat(),
        }
        expired_response = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L3'], json=payload,
        )
        self.assertEqual(expired_response.status_code, 201, expired_response.text)
        expired = OrganizationalSubstitution.objects.get(pk=expired_response.json()['id'])
        self.assertTrue(expired.is_active)
        payload['valid_from'] = (now - timedelta(minutes=1)).isoformat()
        payload['valid_until'] = (now + timedelta(minutes=5)).isoformat()
        replacement_response = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L3'], json=payload,
        )
        self.assertEqual(replacement_response.status_code, 201, replacement_response.text)
        expired.refresh_from_db()
        self.assertFalse(expired.is_active)
        self.assertEqual(expired.ended_at, expired.valid_until)
        self.assertIsNone(expired.ended_by_id)

    def test_l2_cannot_create_substitution(self):
        response = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L2'], json={},
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_l1_substitution_context_is_available_only_to_l1(self):
        response = self.api.get('/api/projects/substitutions/context', headers=self.tokens['L1'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(self.coordination.id, [item['id'] for item in response.json()['coordinations']])
        denied = self.api.get('/api/projects/substitutions/context', headers=self.tokens['L2'])
        self.assertEqual(denied.status_code, 403)

    def test_l3_supervises_an_uncovered_l4_scope_without_inheriting_l4_review(self):
        from clients.models import ProjectLeadership, TeamMembership

        leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.actors['L4'], designated_by=self.actors['L3'],
        )
        TeamMembership.objects.create(
            leadership=leadership, developer=self.actors['L5'], added_by=self.actors['L4'],
        )
        task = Task.objects.create(
            project=self.project, title='Revisión con supervisión', status='En revisión',
            created_by=self.actors['L3'], responsible=self.actors['L4'], assignee=self.actors['L5'],
            assigned_at=timezone.now(),
        )
        appointed = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L3'], json={
                'coordination_id': self.coordination.id, 'leadership_id': leadership.id,
                'absent_level': 'L4', 'absent_person_id': self.actors['L4'].id,
                'substitute_id': None, 'reason': 'Ausencia de L4', 'evidence': 'Constancia',
                'scope': 'Supervisión del ámbito por L3', 'faculties': [],
                'valid_from': (timezone.now() - timedelta(minutes=1)).isoformat(),
                'valid_until': (timezone.now() + timedelta(minutes=5)).isoformat(),
            },
        )
        self.assertEqual(appointed.status_code, 201, appointed.text)
        visible = self.api.get(f'/api/tasks/{task.id}', headers=self.tokens['L3'])
        self.assertEqual(visible.status_code, 200, visible.text)
        self.assertFalse(visible.json()['actions']['can_review'])
        review = self.api.post(
            f'/api/tasks/{task.id}/review', headers=self.tokens['L3'],
            json={'resolution': 'Finalizada', 'reason': 'Intento sin facultad L4'},
        )
        self.assertEqual(review.status_code, 403, review.text)

    def test_l1_designated_l3_substitute_gets_only_time_bounded_task_visibility(self):
        substitute = Collaborator.objects.create(
            first_name='B429', last_name='L3 substitute', document_number='B429-L3-SUB',
            email='b429-l3-sub@example.com', username='b429-l3-sub',
            password_hash=hash_password('test-password'), role=self.actors['L3'].role,
        )
        task = Task.objects.create(
            project=self.project, title='Tarea en coordinación', status='Pendiente',
            created_by=self.actors['L3'], responsible=self.actors['L4'],
        )
        login = self.api.post('/api/auth/login', json={
            'username': 'b429-l3-sub', 'password': 'test-password',
        })
        headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
        started = timezone.now() - timedelta(minutes=2)
        ends = timezone.now() + timedelta(minutes=2)
        self.actors['L3'].is_active = False
        self.actors['L3'].save(update_fields=['is_active'])
        appointed = self.api.post(
            f'/api/projects/{self.project.id}/substitutions', headers=self.tokens['L1'], json={
                'coordination_id': self.coordination.id, 'absent_level': 'L3',
                'absent_person_id': self.actors['L3'].id, 'substitute_id': substitute.id,
                'reason': 'Ausencia L3', 'evidence': 'Constancia de ausencia',
                'scope': 'Coordinación del proyecto', 'faculties': ['tasks.view'],
                'valid_from': started.isoformat(), 'valid_until': ends.isoformat(),
            },
        )
        self.assertEqual(appointed.status_code, 201, appointed.text)
        visible = self.api.get(f'/api/tasks/{task.id}', headers=headers)
        self.assertEqual(visible.status_code, 200, visible.text)
        self.assertFalse(visible.json()['actions']['can_reopen'])
        history = self.api.get(f'/api/projects/{self.project.id}/substitutions', headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual([item['id'] for item in history.json()], [appointed.json()['id']])
        # The substitution currently enables scope-limited visibility only. Mutations remain denied.
        attempted = self.api.post(
            f'/api/projects/{self.project.id}/return-to-execution', headers=headers,
            json={'additional_execution_required': True, 'materially_affects_validation': True,
                  'within_current_commitment': True, 'reason': 'Revisión', 'evidence': 'Informe'},
        )
        self.assertEqual(attempted.status_code, 404, attempted.text)
        expired = self.api.post(
            f'/api/projects/{self.project.id}/substitutions/{appointed.json()["id"]}/end',
            headers=self.tokens['L1'],
        )
        self.assertEqual(expired.status_code, 200, expired.text)
        hidden = self.api.get(f'/api/tasks/{task.id}', headers=headers)
        self.assertEqual(hidden.status_code, 404, hidden.text)

from django.test import TransactionTestCase
from django.utils import timezone
from fastapi.testclient import TestClient
from unittest.mock import patch
from django.db import IntegrityError

from api.main import app
from api.routers.auth import hash_password
from clients.models import (
    Client, Collaborator, Project, ProjectCoordination, ProjectLeadership,
    Role, Task, TaskEvent, TeamMembership, WebCatalog,
)


class TaskWorkflowApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.api = TestClient(app)
        self.people = {}
        self.headers = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'Tareas {level}', level=level)
            self.people[level] = self.make_person(level, role)
        self.people['L3B'] = self.make_person('L3B', Role.objects.get(level='L3'))
        self.people['L4B'] = self.make_person('L4B', Role.objects.get(level='L4'))
        self.people['L5B'] = self.make_person('L5B', Role.objects.get(level='L5'))
        self.people['L5C'] = self.make_person('L5C', Role.objects.get(level='L5'))
        self.people['L2B'] = self.make_person('L2B', Role.objects.get(level='L2'))
        web_type = WebCatalog.objects.create(
            name='Tipo tarea', base_price_rent=10, base_price_sale=100,
        )
        client = Client.objects.create(
            name='Cliente tareas', document_type='DNI', document_number='TASK-CLIENT',
            web_type=web_type, plan='alquiler',
        )
        self.project = Project.objects.create(client=client, name='Proyecto A')
        self.other_project = Project.objects.create(client=client, name='Proyecto B')
        self.coordination = ProjectCoordination.objects.create(
            project=self.project, coordinator=self.people['L3'], assigned_by=self.people['L2'],
        )
        self.other_coordination = ProjectCoordination.objects.create(
            project=self.other_project, coordinator=self.people['L3B'], assigned_by=self.people['L2'],
        )
        self.leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.people['L4'], designated_by=self.people['L3'],
        )
        self.other_leadership = ProjectLeadership.objects.create(
            coordination=self.other_coordination, leader=self.people['L4B'], designated_by=self.people['L3B'],
        )
        self.membership = TeamMembership.objects.create(
            leadership=self.leadership, developer=self.people['L5'], added_by=self.people['L4'],
        )
        self.other_membership = TeamMembership.objects.create(
            leadership=self.other_leadership, developer=self.people['L5B'], added_by=self.people['L4B'],
        )
        for key, person in self.people.items():
            login = self.api.post('/api/auth/login', json={
                'username': person.username, 'password': 'task-password',
            })
            self.assertEqual(login.status_code, 200, login.text)
            self.headers[key] = {'Authorization': f"Bearer {login.json()['access_token']}"}

    @staticmethod
    def make_person(key, role):
        return Collaborator.objects.create(
            first_name=key, last_name='Tarea', document_number=f'TASK-{key}',
            email=f'task-{key.lower()}@example.com', username=f'task-{key.lower()}',
            password_hash=hash_password('task-password'), role=role,
        )

    def create(self, level, *, project=None, status='Pendiente', assignee=None, assignee_id=None, title='Nueva tarea'):
        return self.api.post('/api/tasks/', headers=self.headers[level], json={
            'project_id': (project or self.project).id,
            'title': title,
            'status': status,
            'assignee_id': assignee_id if assignee_id is not None else assignee.id if assignee else None,
        })

    def test_project_designation_chain_checks_roles_and_scope(self):
        response = self.api.post(
            f'/api/tasks/projects/{self.other_project.id}/coordination',
            headers=self.headers['L1'], json={'collaborator_id': self.people['L3'].id},
        )
        self.assertEqual(response.status_code, 403)
        response = self.api.post(
            f'/api/tasks/projects/{self.project.id}/leadership',
            headers=self.headers['L3B'], json={'collaborator_id': self.people['L4'].id},
        )
        self.assertEqual(response.status_code, 404)
        authorized_coordination = self.api.post(
            f'/api/tasks/projects/{self.project.id}/coordination',
            headers=self.headers['L2'], json={'collaborator_id': self.people['L3B'].id},
        )
        self.assertEqual(authorized_coordination.status_code, 201, authorized_coordination.text)
        self.assertEqual(self.api.get('/api/projects/', headers=self.headers['L2']).status_code, 200)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L2']).status_code, 403)
        self.assertEqual(self.create('L2').status_code, 403)
        self.assertEqual(
            self.api.patch(
                f'/api/projects/{self.project.id}', headers=self.headers['L2'],
                json={'status': 'En ejecución'},
            ).status_code,
            405,
        )
        response = self.api.post(
            f'/api/tasks/projects/{self.project.id}/leadership',
            headers=self.headers['L3'], json={'collaborator_id': self.people['L5'].id},
        )
        self.assertEqual(response.status_code, 400)
        response = self.api.post(
            f'/api/tasks/projects/{self.project.id}/leadership',
            headers=self.headers['L3'], json={'collaborator_id': self.people['L4'].id},
        )
        self.assertEqual(response.status_code, 201, response.text)
        response = self.api.post(
            f'/api/tasks/projects/{self.project.id}/team',
            headers=self.headers['L3'], json={'collaborator_id': self.people['L5C'].id},
        )
        self.assertEqual(response.status_code, 403)
        response = self.api.post(
            f'/api/tasks/projects/{self.project.id}/team',
            headers=self.headers['L4'], json={'collaborator_id': self.people['L5C'].id},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertTrue(TeamMembership.objects.filter(
            leadership=self.leadership, developer=self.people['L5C'], is_active=True,
        ).exists())

    def test_l3_creates_pending_only_in_coordinated_project(self):
        response = self.create('L3')
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['status'], 'Pendiente')
        self.assertEqual(response.json()['responsible_id'], self.people['L3'].id)
        unauthorized = self.create('L3B')
        self.assertEqual(unauthorized.status_code, 403)
        direct_assignment = self.create('L3', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(direct_assignment.status_code, 403)
        self.assertEqual(Task.objects.count(), 1)

    def test_l4_pending_direct_assignment_and_initial_assignment(self):
        pending = self.create('L4', title='Pendiente de equipo')
        assigned = self.create('L4', status='Asignada', assignee=self.people['L5'], title='Asignada al equipo')
        self.assertEqual(pending.status_code, 201, pending.text)
        self.assertEqual(assigned.status_code, 201, assigned.text)
        self.assertEqual(assigned.json()['assignee_id'], self.people['L5'].id)
        self.assertEqual(Task.objects.get(pk=assigned.json()['id']).events.count(), 1)

        response = self.api.post(
            f"/api/tasks/{pending.json()['id']}/assignment",
            headers=self.headers['L4'], json={'assignee_id': self.people['L5'].id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        pending_refresh = Task.objects.get(pk=pending.json()['id'])
        self.assertEqual(pending_refresh.status, 'Asignada')
        self.assertEqual(pending_refresh.responsible_id, self.people['L4'].id)
        self.assertEqual(pending_refresh.events.count(), 2)
        for level in ('L1', 'L2', 'L3', 'L5'):
            denied = self.api.post(
                f"/api/tasks/{pending.json()['id']}/assignment",
                headers=self.headers[level], json={'assignee_id': self.people['L5'].id},
            )
            self.assertEqual(denied.status_code, 403, level)

    def test_foreign_team_or_inactive_developer_is_rejected_without_partial_rows(self):
        before_tasks, before_events = Task.objects.count(), TaskEvent.objects.count()
        foreign = self.create('L4', status='Asignada', assignee=self.people['L5B'])
        self.assertEqual(foreign.status_code, 400)
        nonexistent = self.create('L4', status='Asignada', assignee_id=999999)
        self.assertEqual(nonexistent.status_code, 400)
        pending = self.create('L4')
        self.assertEqual(pending.status_code, 201)
        before_events = TaskEvent.objects.count()
        response = self.api.post(
            f"/api/tasks/{pending.json()['id']}/assignment",
            headers=self.headers['L4'], json={'assignee_id': self.people['L5B'].id},
        )
        self.assertEqual(response.status_code, 400)
        inactive = self.people['L5']
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        response = self.create('L4', status='Asignada', assignee=inactive)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Task.objects.count(), before_tasks + 1)
        self.assertEqual(TaskEvent.objects.count(), before_events)

    def test_only_approved_levels_create_and_operational_reads_are_scoped(self):
        task = Task.objects.create(
            project=self.project, title='Tarea de consulta', status='Asignada',
            created_by=self.people['L4'], responsible=self.people['L4'],
            assignee=self.people['L5'], assigned_at=timezone.now(),
        )
        TaskEvent.objects.create(
            task=task, event_type='creada', actor=self.people['L4'],
            new_status='Asignada', assignee=self.people['L5'],
        )
        for level in ('L1', 'L2', 'L5'):
            self.assertEqual(self.create(level).status_code, 403, level)
        for level in ('L1', 'L2'):
            self.assertEqual(self.api.get('/api/tasks/', headers=self.headers[level]).status_code, 403)
        self.assertEqual(self.api.get('/api/tasks/context', headers=self.headers['L1']).status_code, 403)
        self.assertEqual(self.api.get('/api/tasks/context', headers=self.headers['L2']).status_code, 200)
        for level in ('L3', 'L4', 'L5'):
            response = self.api.get('/api/tasks/', headers=self.headers[level])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([item['id'] for item in response.json()], [task.id])
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L3B']).json(), [])
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L4B']).json(), [])
        other_task = Task.objects.create(
            project=self.other_project, title='Privada de otro L5', status='Asignada',
            created_by=self.people['L4B'], responsible=self.people['L4B'],
            assignee=self.people['L5B'], assigned_at=timezone.now(),
        )
        detail = self.api.get(f'/api/tasks/{other_task.id}', headers=self.headers['L5'])
        self.assertEqual(detail.status_code, 404)
        own = self.api.get('/api/tasks/', headers=self.headers['L5B'])
        self.assertEqual([item['id'] for item in own.json()], [other_task.id])

    def test_l4_scope_excludes_another_leaders_tasks_in_the_same_project(self):
        second_leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.people['L4B'], designated_by=self.people['L3'],
        )
        TeamMembership.objects.create(
            leadership=second_leadership, developer=self.people['L5C'], added_by=self.people['L4B'],
        )
        another_leader_task = self.create('L4', title='Responsabilidad exclusiva')
        self.assertEqual(another_leader_task.status_code, 201, another_leader_task.text)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L4B']).json(), [])
        denied = self.api.post(
            f"/api/tasks/{another_leader_task.json()['id']}/assignment",
            headers=self.headers['L4B'], json={'assignee_id': self.people['L5C'].id},
        )
        self.assertEqual(denied.status_code, 404)

        coordinated_pending = self.create('L3', title='Pendiente bajo coordinación')
        self.assertEqual(coordinated_pending.status_code, 201, coordinated_pending.text)
        scoped = self.api.get('/api/tasks/', headers=self.headers['L4B'])
        self.assertEqual([item['id'] for item in scoped.json()], [coordinated_pending.json()['id']])

    def test_l4_tasks_are_scoped_to_the_specific_coordinating_l3(self):
        second_coordination = ProjectCoordination.objects.create(
            project=self.project, coordinator=self.people['L3B'], assigned_by=self.people['L2'],
        )
        second_leadership = ProjectLeadership.objects.create(
            coordination=second_coordination, leader=self.people['L4B'], designated_by=self.people['L3B'],
        )
        TeamMembership.objects.create(
            leadership=second_leadership, developer=self.people['L5C'], added_by=self.people['L4B'],
        )
        task_a = self.create('L3', title='Trabajo de coordinación A')
        task_b = self.create('L3B', title='Trabajo de coordinación B')
        self.assertEqual(task_a.status_code, 201, task_a.text)
        self.assertEqual(task_b.status_code, 201, task_b.text)
        l4a = self.api.get('/api/tasks/', headers=self.headers['L4'])
        l4b = self.api.get('/api/tasks/', headers=self.headers['L4B'])
        self.assertEqual([item['id'] for item in l4a.json()], [task_a.json()['id']])
        self.assertEqual([item['id'] for item in l4b.json()], [task_b.json()['id']])
        assignment = self.api.post(
            f"/api/tasks/{task_a.json()['id']}/assignment",
            headers=self.headers['L4B'], json={'assignee_id': self.people['L5C'].id},
        )
        self.assertEqual(assignment.status_code, 404)

    def test_task_operations_do_not_change_project_status(self):
        before_status = self.project.status
        response = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(response.status_code, 201, response.text)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, before_status)

    def test_l2_withdrawal_cascades_scope_and_keeps_assigned_task_for_l5(self):
        assigned = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(assigned.status_code, 201, assigned.text)
        task_id = assigned.json()['id']
        original_event_count = TaskEvent.objects.filter(task_id=task_id).count()
        denied = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/coordination/{self.people["L3"].id}',
            headers=self.headers['L3'],
        )
        self.assertEqual(denied.status_code, 403)
        other_designator = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/coordination/{self.people["L3"].id}',
            headers=self.headers['L2B'],
        )
        self.assertEqual(other_designator.status_code, 404)
        response = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/coordination/{self.people["L3"].id}',
            headers=self.headers['L2'],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.coordination.refresh_from_db()
        self.leadership.refresh_from_db()
        self.membership.refresh_from_db()
        self.assertFalse(self.coordination.is_active)
        self.assertFalse(self.leadership.is_active)
        self.assertFalse(self.membership.is_active)
        self.assertEqual(self.membership.ended_by_id, self.people['L2'].id)
        self.assertTrue(Task.objects.filter(pk=task_id).exists())
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), original_event_count)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L3']).json(), [])
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L4']).json(), [])
        self.assertEqual(
            self.api.get(f"/api/tasks/{assigned.json()['id']}", headers=self.headers['L5']).status_code,
            200,
        )
        self.assertEqual(self.create('L4').status_code, 403)

    def test_l3_withdrawal_preserves_history_and_can_redesignate(self):
        task = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(task.status_code, 201, task.text)
        task_id = task.json()['id']
        self.assertEqual(self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5']).status_code, 200)
        self.assertEqual(self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Resultado esperando revisión'},
        ).status_code, 200)
        original_event_count = TaskEvent.objects.filter(task_id=task_id).count()
        other_leader = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/leadership/{self.people["L4"].id}',
            headers=self.headers['L3B'],
        )
        self.assertEqual(other_leader.status_code, 404)
        response = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/leadership/{self.people["L4"].id}',
            headers=self.headers['L3'],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.leadership.refresh_from_db()
        self.membership.refresh_from_db()
        self.assertFalse(self.leadership.is_active)
        self.assertFalse(self.membership.is_active)
        self.assertEqual(self.membership.ended_by_id, self.people['L3'].id)
        self.assertTrue(Task.objects.filter(pk=task_id).exists())
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), original_event_count)
        stale_review = self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Finalizada'},
        )
        self.assertEqual(stale_review.status_code, 404)
        self.assertEqual(Task.objects.get(pk=task_id).status, 'En revisión')
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), original_event_count)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L4']).json(), [])
        self.assertEqual(self.api.get(f"/api/tasks/{task.json()['id']}", headers=self.headers['L5']).status_code, 200)
        again = self.api.post(
            f'/api/tasks/projects/{self.project.id}/leadership',
            headers=self.headers['L3'], json={'collaborator_id': self.people['L4'].id},
        )
        self.assertEqual(again.status_code, 201, again.text)
        self.assertEqual(ProjectLeadership.objects.filter(coordination=self.coordination).count(), 2)
        self.assertEqual(ProjectLeadership.objects.filter(coordination=self.coordination, is_active=True).count(), 1)

    def test_l4_withdrawal_keeps_assigned_work_readable_and_can_readd_member(self):
        task = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(task.status_code, 201, task.text)
        task_id = task.json()['id']
        original_event_count = TaskEvent.objects.filter(task_id=task_id).count()
        denied = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/team/{self.people["L5"].id}',
            headers=self.headers['L4B'],
        )
        self.assertEqual(denied.status_code, 404)
        response = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/team/{self.people["L5"].id}',
            headers=self.headers['L4'],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.is_active)
        self.assertTrue(Task.objects.filter(pk=task_id).exists())
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), original_event_count)
        self.assertEqual(self.api.get(f"/api/tasks/{task_id}", headers=self.headers['L5']).status_code, 200)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers['L5']).json()[0]['id'], task_id)
        denied_history_mutation = self.api.post(
            f'/api/tasks/{task_id}/assignment', headers=self.headers['L5'],
            json={'assignee_id': self.people['L5'].id},
        )
        self.assertEqual(denied_history_mutation.status_code, 403)
        blocked_assignment = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(blocked_assignment.status_code, 400)
        readd = self.api.post(
            f'/api/tasks/projects/{self.project.id}/team',
            headers=self.headers['L4'], json={'collaborator_id': self.people['L5'].id},
        )
        self.assertEqual(readd.status_code, 201, readd.text)
        self.assertEqual(TeamMembership.objects.filter(leadership=self.leadership, developer=self.people['L5']).count(), 2)

    def test_ordinary_task_cycle_preserves_each_result_observation_and_resolution(self):
        response = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(response.status_code, 201, response.text)
        task_id = response.json()['id']
        project_status = self.project.status

        started = self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()['status'], 'En proceso')

        self.assertEqual(
            self.api.post(f'/api/tasks/{task_id}/review', headers=self.headers['L5'],
                          json={'resolution': 'Finalizada'}).status_code,
            403,
        )
        empty_result = self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': '   '},
        )
        self.assertEqual(empty_result.status_code, 422)
        self.assertEqual(Task.objects.get(pk=task_id).status, 'En proceso')
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), 2)

        first_submission = self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Resultado ciclo uno'},
        )
        self.assertEqual(first_submission.status_code, 200, first_submission.text)
        self.assertEqual(first_submission.json()['status'], 'En revisión')
        self.assertTrue(first_submission.json()['events'][-1]['result_text'] == 'Resultado ciclo uno')

        foreign_review = self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4B'],
            json={'resolution': 'Observada', 'reason': 'Corrección necesaria'},
        )
        self.assertEqual(foreign_review.status_code, 404)
        missing_reason = self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Observada'},
        )
        self.assertEqual(missing_reason.status_code, 422)
        observed = self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Observada', 'reason': 'Falta documentar el cambio'},
        )
        self.assertEqual(observed.status_code, 200, observed.text)
        self.assertEqual(observed.json()['status'], 'Observada')
        self.assertTrue(observed.json()['events'][-1]['reason'])
        l5_observed = self.api.get(f'/api/tasks/{task_id}', headers=self.headers['L5'])
        self.assertTrue(l5_observed.json()['actions']['can_start'])

        corrected = self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.assertEqual(corrected.json()['events'][-1]['event_type'], 'correccion_iniciada')
        second_submission = self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Resultado ciclo dos corregido'},
        )
        self.assertEqual(second_submission.status_code, 200, second_submission.text)
        approved = self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Finalizada'},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['status'], 'Finalizada')
        events = list(TaskEvent.objects.filter(task_id=task_id))
        self.assertEqual(
            [event.event_type for event in events],
            ['creada', 'iniciada', 'resultado_presentado', 'observada',
             'correccion_iniciada', 'resultado_presentado', 'aprobada_revision'],
        )
        submissions = [event.result_text for event in events if event.event_type == 'resultado_presentado']
        self.assertEqual(submissions, ['Resultado ciclo uno', 'Resultado ciclo dos corregido'])
        self.assertEqual(events[3].reason, 'Falta documentar el cambio')
        self.assertEqual(events[-1].previous_status, 'En revisión')
        self.assertEqual(events[-1].new_status, 'Finalizada')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_transition_rejections_and_withdrawn_membership_leave_task_and_history_unchanged(self):
        response = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(response.status_code, 201, response.text)
        task_id = response.json()['id']
        before_events = TaskEvent.objects.filter(task_id=task_id).count()
        invalid_submission = self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'No se inició'},
        )
        self.assertEqual(invalid_submission.status_code, 409)
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), before_events)

        withdrawn = self.api.delete(
            f'/api/tasks/projects/{self.project.id}/team/{self.people["L5"].id}',
            headers=self.headers['L4'],
        )
        self.assertEqual(withdrawn.status_code, 200)
        denied_start = self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.assertEqual(denied_start.status_code, 404)
        history = self.api.get(f'/api/tasks/{task_id}', headers=self.headers['L5'])
        self.assertEqual(history.status_code, 200)
        self.assertFalse(history.json()['actions']['can_start'])
        self.assertFalse(history.json()['actions']['can_submit_result'])
        task = Task.objects.get(pk=task_id)
        self.assertEqual(task.status, 'Asignada')
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), before_events)

    def test_failed_event_write_rolls_back_task_transition(self):
        response = self.create('L4', status='Asignada', assignee=self.people['L5'])
        self.assertEqual(response.status_code, 201, response.text)
        task_id = response.json()['id']
        before_events = TaskEvent.objects.filter(task_id=task_id).count()
        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed_start = self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.assertEqual(failed_start.status_code, 409)
        task = Task.objects.get(pk=task_id)
        self.assertEqual(task.status, 'Asignada')
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), before_events)

    def test_l4_reassignment_preserves_execution_and_observation_history(self):
        self.api.post(
            f'/api/tasks/projects/{self.project.id}/team', headers=self.headers['L4'],
            json={'collaborator_id': self.people['L5C'].id},
        )
        first = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = first.json()['id']
        self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        project_status = self.project.status
        reassigned = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
            json={'assignee_id': self.people['L5C'].id, 'reason': 'Redistribución interna'},
        )
        self.assertEqual(reassigned.status_code, 200, reassigned.text)
        self.assertEqual(reassigned.json()['status'], 'Asignada')
        self.assertEqual(reassigned.json()['assignee_id'], self.people['L5C'].id)
        event = reassigned.json()['events'][-1]
        self.assertEqual(event['previous_assignee_id'], self.people['L5'].id)
        self.assertEqual(event['assignee_id'], self.people['L5C'].id)
        self.assertEqual(event['responsible_id'], self.people['L4'].id)
        self.assertEqual(event['previous_status'], 'En proceso')
        self.assertEqual(event['new_status'], 'Asignada')
        self.assertEqual(event['reason'], 'Redistribución interna')

        second = self.create('L4', status='Asignada', assignee=self.people['L5'])
        second_id = second.json()['id']
        self.api.post(f'/api/tasks/{second_id}/start', headers=self.headers['L5'])
        self.api.post(
            f'/api/tasks/{second_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Entrega preservada'},
        )
        self.api.post(
            f'/api/tasks/{second_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Observada', 'reason': 'Debe corregirse el detalle'},
        )
        observed_reassignment = self.api.post(
            f'/api/tasks/{second_id}/reassignment', headers=self.headers['L4'],
            json={'assignee_id': self.people['L5C'].id, 'reason': 'Cambio de ejecutor para corregir'},
        )
        self.assertEqual(observed_reassignment.status_code, 200, observed_reassignment.text)
        self.assertEqual(observed_reassignment.json()['status'], 'Observada')
        events = observed_reassignment.json()['events']
        self.assertEqual(events[-1]['previous_status'], 'Observada')
        self.assertEqual(events[-1]['new_status'], 'Observada')
        self.assertEqual(events[2]['result_text'], 'Entrega preservada')
        self.assertEqual(events[3]['reason'], 'Debe corregirse el detalle')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_l3_reassigns_between_teams_and_l4_cannot_cross_team(self):
        self.api.post(
            f'/api/tasks/projects/{self.project.id}/team', headers=self.headers['L4'],
            json={'collaborator_id': self.people['L5C'].id},
        )
        second_leadership = ProjectLeadership.objects.create(
            coordination=self.coordination, leader=self.people['L4B'], designated_by=self.people['L3'],
        )
        TeamMembership.objects.create(
            leadership=second_leadership, developer=self.people['L5B'], added_by=self.people['L4B'],
        )
        first = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = first.json()['id']
        self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])

        forbidden = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
            json={
                'assignee_id': self.people['L5B'].id,
                'responsible_id': self.people['L4B'].id,
                'reason': 'Debe denegarse al L4 ajeno',
            },
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(Task.objects.get(pk=task_id).assignee_id, self.people['L5'].id)

        moved = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L3'],
            json={
                'assignee_id': self.people['L5B'].id,
                'responsible_id': self.people['L4B'].id,
                'reason': 'Reorganización entre equipos',
            },
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()['status'], 'Asignada')
        self.assertEqual(moved.json()['responsible_id'], self.people['L4B'].id)
        event = moved.json()['events'][-1]
        self.assertEqual(event['previous_responsible_id'], self.people['L4'].id)
        self.assertEqual(event['responsible_id'], self.people['L4B'].id)

    def test_open_review_blocks_reassignment_and_executor_removal_without_partial_changes(self):
        self.api.post(
            f'/api/tasks/projects/{self.project.id}/team', headers=self.headers['L4'],
            json={'collaborator_id': self.people['L5C'].id},
        )
        first = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = first.json()['id']
        self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Presentación pendiente'},
        )
        before = list(TaskEvent.objects.filter(task_id=task_id).values_list('event_type', 'reason'))
        reassignment = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
            json={'assignee_id': self.people['L5C'].id, 'reason': 'Intento no permitido'},
        )
        withdrawal = self.api.post(
            f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L4'],
            json={'reason': 'Intento no permitido'},
        )
        self.assertEqual(reassignment.status_code, 409)
        self.assertEqual(withdrawal.status_code, 409)
        task = Task.objects.get(pk=task_id)
        self.assertEqual((task.status, task.assignee_id), ('En revisión', self.people['L5'].id))
        self.assertEqual(list(TaskEvent.objects.filter(task_id=task_id).values_list('event_type', 'reason')), before)

    def test_executor_withdrawal_returns_assigned_or_running_task_to_pending_with_history(self):
        project_status = self.project.status
        for status in ('Asignada', 'En proceso'):
            created = self.create('L4', status='Asignada', assignee=self.people['L5'])
            task_id = created.json()['id']
            if status == 'En proceso':
                self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
            removed = self.api.post(
                f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L4'],
                json={'reason': f'Retiro motivado desde {status}'},
            )
            self.assertEqual(removed.status_code, 200, removed.text)
            task = Task.objects.get(pk=task_id)
            self.assertEqual((task.status, task.assignee_id, task.assigned_at), ('Pendiente', None, None))
            event = removed.json()['events'][-1]
            self.assertEqual(event['event_type'], 'ejecutor_retirado')
            self.assertEqual(event['previous_status'], status)
            self.assertEqual(event['new_status'], 'Pendiente')
            self.assertEqual(event['previous_assignee_id'], self.people['L5'].id)
            self.assertIsNone(event['assignee_id'])
            self.assertEqual(event['responsible_id'], self.people['L4'].id)
            self.assertTrue(event['reason'])
            self.assertEqual(removed.json()['responsible_id'], self.people['L4'].id)
            self.assertEqual(self.api.get(f'/api/tasks/{task_id}', headers=self.headers['L5']).status_code, 404)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_reassignment_and_removal_denials_do_not_change_assignment_or_history(self):
        self.api.post(
            f'/api/tasks/projects/{self.project.id}/team', headers=self.headers['L4'],
            json={'collaborator_id': self.people['L5C'].id},
        )
        created = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = created.json()['id']
        self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        initial_events = TaskEvent.objects.filter(task_id=task_id).count()

        no_membership = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
            json={'assignee_id': self.people['L5B'].id, 'reason': 'Ejecutor externo'},
        )
        foreign_l4 = self.api.post(
            f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L4B'],
            json={'reason': 'Fuera de ámbito'},
        )
        denied_l5 = self.api.post(
            f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L5'],
            json={'reason': 'Sin competencia'},
        )
        self.assertEqual(no_membership.status_code, 400)
        self.assertEqual(foreign_l4.status_code, 404)
        self.assertEqual(denied_l5.status_code, 403)
        task = Task.objects.get(pk=task_id)
        self.assertEqual((task.status, task.assignee_id), ('En proceso', self.people['L5'].id))
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), initial_events)

        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed_reassignment = self.api.post(
                f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
                json={'assignee_id': self.people['L5C'].id, 'reason': 'Falla de historial'},
            )
        self.assertEqual(failed_reassignment.status_code, 409)
        task.refresh_from_db()
        self.assertEqual((task.status, task.assignee_id), ('En proceso', self.people['L5'].id))
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), initial_events)

        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed_removal = self.api.post(
                f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L4'],
                json={'reason': 'Falla de historial'},
            )
        self.assertEqual(failed_removal.status_code, 409)
        task.refresh_from_db()
        self.assertEqual((task.status, task.assignee_id), ('En proceso', self.people['L5'].id))
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), initial_events)

    def test_finalized_tasks_do_not_accept_reassignment_or_executor_removal(self):
        created = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = created.json()['id']
        self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.api.post(
            f'/api/tasks/{task_id}/submit-review', headers=self.headers['L5'],
            json={'result_text': 'Resultado aprobado'},
        )
        self.api.post(
            f'/api/tasks/{task_id}/review', headers=self.headers['L4'],
            json={'resolution': 'Finalizada'},
        )
        event_count = TaskEvent.objects.filter(task_id=task_id).count()
        for route, payload in (
            ('reassignment', {'assignee_id': self.people['L5'].id, 'reason': 'No permitida'}),
            ('remove-executor', {'reason': 'No permitida'}),
        ):
            denied = self.api.post(
                f'/api/tasks/{task_id}/{route}', headers=self.headers['L4'], json=payload,
            )
            self.assertEqual(denied.status_code, 409)
        task = Task.objects.get(pk=task_id)
        self.assertEqual((task.status, task.assignee_id), ('Finalizada', self.people['L5'].id))
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), event_count)
        block_finalized = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L4'],
            json={'reason': 'No hay una ejecución abierta'},
        )
        self.assertEqual(block_finalized.status_code, 409)
        self.assertFalse(Task.objects.get(pk=task_id).is_blocked)
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), event_count)

    def test_l4_and_l3_block_and_unblock_with_history_without_changing_ordinary_status(self):
        created = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = created.json()['id']
        project_status = self.project.status
        initial_events = TaskEvent.objects.filter(task_id=task_id).count()
        missing_reason = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L4'],
            json={'reason': '   '},
        )
        self.assertEqual(missing_reason.status_code, 422)
        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed_block = self.api.post(
                f'/api/tasks/{task_id}/block', headers=self.headers['L4'],
                json={'reason': 'No dejar cambio sin evento'},
            )
        self.assertEqual(failed_block.status_code, 409)
        self.assertFalse(Task.objects.get(pk=task_id).is_blocked)
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), initial_events)

        blocked = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L4'],
            json={'reason': 'Dependencia externa detenida', 'evidence': 'Ticket INC-204'},
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)
        self.assertEqual(blocked.json()['status'], 'Asignada')
        self.assertTrue(blocked.json()['is_blocked'])
        self.assertEqual(blocked.json()['block_reason'], 'Dependencia externa detenida')
        self.assertEqual(blocked.json()['block_evidence'], 'Ticket INC-204')
        declared = blocked.json()['events'][-1]
        self.assertEqual(declared['event_type'], 'bloqueo_declarado')
        self.assertFalse(declared['is_blocked_before'])
        self.assertTrue(declared['is_blocked_after'])
        self.assertEqual(declared['previous_status'], 'Asignada')
        self.assertEqual(declared['new_status'], 'Asignada')
        event_count = TaskEvent.objects.filter(task_id=task_id).count()

        repeated = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L3'],
            json={'reason': 'Segundo bloqueo'},
        )
        self.assertEqual(repeated.status_code, 409)
        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed_unblock = self.api.post(
                f'/api/tasks/{task_id}/unblock', headers=self.headers['L3'],
                json={'reason': 'No levantar sin evento'},
            )
        self.assertEqual(failed_unblock.status_code, 409)
        still_blocked = Task.objects.get(pk=task_id)
        self.assertTrue(still_blocked.is_blocked)
        self.assertEqual(still_blocked.block_reason, 'Dependencia externa detenida')
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), event_count)
        unblocked = self.api.post(
            f'/api/tasks/{task_id}/unblock', headers=self.headers['L3'],
            json={'reason': 'Dependencia resuelta', 'evidence': 'Ticket cerrado'},
        )
        self.assertEqual(unblocked.status_code, 200, unblocked.text)
        self.assertEqual(unblocked.json()['status'], 'Asignada')
        self.assertFalse(unblocked.json()['is_blocked'])
        self.assertEqual(unblocked.json()['block_reason'], '')
        self.assertEqual(unblocked.json()['events'][-1]['event_type'], 'bloqueo_levantado')
        self.assertTrue(unblocked.json()['events'][-1]['is_blocked_before'])
        self.assertFalse(unblocked.json()['events'][-1]['is_blocked_after'])
        self.assertEqual(unblocked.json()['events'][-1]['reason'], 'Dependencia resuelta')
        self.assertEqual(unblocked.json()['events'][-1]['evidence'], 'Ticket cerrado')
        no_current_block = self.api.post(
            f'/api/tasks/{task_id}/unblock', headers=self.headers['L4'],
            json={'reason': 'Levantamiento repetido'},
        )
        self.assertEqual(no_current_block.status_code, 409)
        l3_blocked = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L3'],
            json={'reason': 'Impedimento dentro de coordinación'},
        )
        self.assertEqual(l3_blocked.status_code, 200, l3_blocked.text)
        self.assertEqual(l3_blocked.json()['events'][-1]['actor_id'], self.people['L3'].id)
        l4_unblocked = self.api.post(
            f'/api/tasks/{task_id}/unblock', headers=self.headers['L4'],
            json={'reason': 'Recurso restablecido'},
        )
        self.assertEqual(l4_unblocked.status_code, 200, l4_unblocked.text)
        self.assertEqual(l4_unblocked.json()['events'][-1]['actor_id'], self.people['L4'].id)
        task = Task.objects.get(pk=task_id)
        self.assertEqual((task.status, task.is_blocked), ('Asignada', False))
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_block_permissions_reject_out_of_scope_roles_and_withdrawn_l4_relation(self):
        created = self.create('L4B', status='Asignada', assignee=self.people['L5B'], project=self.other_project)
        task_id = created.json()['id']
        denied = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L3'],
            json={'reason': 'Fuera de coordinación'},
        )
        self.assertEqual(denied.status_code, 404)
        for level in ('L1', 'L2', 'L5'):
            response = self.api.post(
                f'/api/tasks/{task_id}/block', headers=self.headers[level],
                json={'reason': 'No autorizado'},
            )
            self.assertEqual(response.status_code, 403)

        self.api.delete(
            f'/api/tasks/projects/{self.other_project.id}/leadership/{self.people["L4B"].id}',
            headers=self.headers['L3B'],
        )
        withdrawn_l4 = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L4B'],
            json={'reason': 'Relación retirada'},
        )
        self.assertEqual(withdrawn_l4.status_code, 404)
        self.assertFalse(Task.objects.get(pk=task_id).is_blocked)
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id).count(), 1)

    def test_l5_reports_incident_without_setting_or_clearing_block_condition(self):
        created = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = created.json()['id']
        self.assertEqual(self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L5'],
            json={'reason': 'Unilateral'},
        ).status_code, 403)
        reported = self.api.post(
            f'/api/tasks/{task_id}/incident', headers=self.headers['L5'],
            json={'reason': 'No hay acceso al entorno', 'evidence': 'Captura adjunta por referencia'},
        )
        self.assertEqual(reported.status_code, 200, reported.text)
        self.assertFalse(reported.json()['is_blocked'])
        self.assertEqual(reported.json()['status'], 'Asignada')
        event = reported.json()['events'][-1]
        self.assertEqual(event['event_type'], 'incidencia_comunicada')
        self.assertEqual(event['actor_id'], self.people['L5'].id)
        self.assertFalse(event['is_blocked_before'])
        self.assertFalse(event['is_blocked_after'])
        self.assertEqual(event['reason'], 'No hay acceso al entorno')
        self.assertEqual(event['evidence'], 'Captura adjunta por referencia')
        self.assertEqual(self.api.post(
            f'/api/tasks/{task_id}/unblock', headers=self.headers['L5'],
            json={'reason': 'Unilateral'},
        ).status_code, 403)

    def test_b4_04_and_b4_05_flows_preserve_block_condition_and_history(self):
        self.api.post(
            f'/api/tasks/projects/{self.project.id}/team', headers=self.headers['L4'],
            json={'collaborator_id': self.people['L5C'].id},
        )
        created = self.create('L4', status='Asignada', assignee=self.people['L5'])
        task_id = created.json()['id']
        blocked = self.api.post(
            f'/api/tasks/{task_id}/block', headers=self.headers['L4'],
            json={'reason': 'Bloqueo de ejecución'},
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)

        # T-03 no define una prohibición universal para las transiciones ordinarias;
        # los flujos autorizados conservan el indicador hasta que se levante explícitamente.
        started = self.api.post(f'/api/tasks/{task_id}/start', headers=self.headers['L5'])
        self.assertEqual(started.status_code, 200, started.text)
        self.assertTrue(started.json()['is_blocked'])
        self.assertTrue(started.json()['events'][-1]['is_blocked_before'])
        self.assertTrue(started.json()['events'][-1]['is_blocked_after'])
        reassigned = self.api.post(
            f'/api/tasks/{task_id}/reassignment', headers=self.headers['L4'],
            json={'assignee_id': self.people['L5C'].id, 'reason': 'Cambio del ejecutor'},
        )
        self.assertEqual(reassigned.status_code, 200, reassigned.text)
        self.assertEqual(reassigned.json()['status'], 'Asignada')
        self.assertTrue(reassigned.json()['is_blocked'])
        self.assertTrue(reassigned.json()['events'][-1]['is_blocked_before'])
        self.assertTrue(reassigned.json()['events'][-1]['is_blocked_after'])
        event_types = [item['event_type'] for item in reassigned.json()['events']]
        self.assertIn('bloqueo_declarado', event_types)
        self.assertIn('ejecutor_reasignado', event_types)

        removed = self.api.post(
            f'/api/tasks/{task_id}/remove-executor', headers=self.headers['L4'],
            json={'reason': 'Retirada sin reemplazo'},
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()['status'], 'Pendiente')
        self.assertTrue(removed.json()['is_blocked'])
        self.assertEqual(removed.json()['events'][-1]['event_type'], 'ejecutor_retirado')
        self.assertTrue(removed.json()['events'][-1]['is_blocked_before'])
        self.assertTrue(removed.json()['events'][-1]['is_blocked_after'])

    def make_finalized_task(self, project=None):
        project = project or self.project
        task = Task.objects.create(
            project=project, title='Resultado aprobado', status='Finalizada',
            created_by=self.people['L4'], responsible=self.people['L4'],
            assignee=self.people['L5'], assigned_at=timezone.now(),
        )
        approval = TaskEvent.objects.create(
            task=task, event_type='aprobada_revision', actor=self.people['L4'],
            previous_status='En revisión', new_status='Finalizada',
            assignee=self.people['L5'], result_text='Entrega aprobada originalmente',
            reason='Aprobación inicial',
        )
        return task, approval

    def test_l3_reopens_finalized_task_and_preserves_approval_and_project(self):
        task, approval = self.make_finalized_task()
        project_status = self.project.status
        visible = self.api.get(f'/api/tasks/{task.id}', headers=self.headers['L3'])
        self.assertTrue(visible.json()['actions']['can_reopen'])
        response = self.api.post(
            f'/api/tasks/{task.id}/reopen', headers=self.headers['L3'],
            json={'reason': 'Se detectó una deficiencia técnica',
                  'result_text': 'Corregir el cálculo y presentar evidencia actualizada'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'Observada')
        self.assertFalse(response.json()['actions']['can_reopen'])
        self.assertEqual(len(response.json()['events']), 2)
        reopened = response.json()['events'][-1]
        self.assertEqual(reopened['event_type'], 'reapertura_autorizada')
        self.assertEqual(reopened['task_id'], task.id)
        self.assertTrue(reopened['occurred_at'])
        self.assertEqual(reopened['actor_id'], self.people['L3'].id)
        self.assertEqual(reopened['previous_status'], 'Finalizada')
        self.assertEqual(reopened['new_status'], 'Observada')
        self.assertEqual(reopened['reason'], 'Se detectó una deficiencia técnica')
        self.assertEqual(reopened['result_text'], 'Corregir el cálculo y presentar evidencia actualizada')
        approval.refresh_from_db()
        self.assertEqual(approval.new_status, 'Finalizada')
        self.assertEqual(approval.result_text, 'Entrega aprobada originalmente')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_reopen_denies_other_levels_foreign_coordination_and_invalid_states(self):
        task, _approval = self.make_finalized_task()
        before_events = TaskEvent.objects.filter(task=task).count()
        payload = {'reason': 'Defecto comprobado', 'result_text': 'Corregir el defecto'}
        for level in ('L1', 'L2', 'L4', 'L5'):
            denied = self.api.post(
                f'/api/tasks/{task.id}/reopen', headers=self.headers[level], json=payload,
            )
            self.assertEqual(denied.status_code, 403, f'{level}: {denied.text}')
        foreign = self.api.post(
            f'/api/tasks/{task.id}/reopen', headers=self.headers['L3B'], json=payload,
        )
        self.assertEqual(foreign.status_code, 404)
        task.status = 'En revisión'
        task.save(update_fields=['status'])
        incompatible = self.api.post(
            f'/api/tasks/{task.id}/reopen', headers=self.headers['L3'], json=payload,
        )
        self.assertEqual(incompatible.status_code, 409)
        missing = self.api.post(
            f'/api/tasks/{task.id}/reopen', headers=self.headers['L3'],
            json={'reason': ' ', 'result_text': ' '},
        )
        self.assertEqual(missing.status_code, 422)
        task.refresh_from_db()
        self.assertEqual(task.status, 'En revisión')
        self.assertEqual(TaskEvent.objects.filter(task=task).count(), before_events)

    def test_reopen_remains_under_l3_followup_without_current_l4_or_executor_membership(self):
        task, _approval = self.make_finalized_task()
        self.leadership.is_active = False
        self.leadership.save(update_fields=['is_active'])
        self.membership.is_active = False
        self.membership.save(update_fields=['is_active'])
        response = self.api.post(
            f'/api/tasks/{task.id}/reopen', headers=self.headers['L3'],
            json={'reason': 'Corrección necesaria', 'result_text': 'Esperar ejecutor autorizado'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'Observada')
        self.assertFalse(response.json()['actions']['can_reopen'])
        detail = self.api.get(f'/api/tasks/{task.id}', headers=self.headers['L5'])
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.json()['actions']['can_start'])
        denied_start = self.api.post(f'/api/tasks/{task.id}/start', headers=self.headers['L5'])
        self.assertEqual(denied_start.status_code, 404)

    def test_failed_reopen_event_rolls_back_status_change(self):
        task, _approval = self.make_finalized_task()
        before_events = TaskEvent.objects.filter(task=task).count()
        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            response = self.api.post(
                f'/api/tasks/{task.id}/reopen', headers=self.headers['L3'],
                json={'reason': 'Defecto técnico', 'result_text': 'Corregir resultado'},
            )
        self.assertEqual(response.status_code, 409)
        task.refresh_from_db()
        self.assertEqual(task.status, 'Finalizada')
        self.assertEqual(TaskEvent.objects.filter(task=task).count(), before_events)

    def create_cancelable_task(self, *, project=None):
        response = self.create('L4', project=project, status='Asignada', assignee=self.people['L5'])
        self.assertEqual(response.status_code, 201, response.text)
        return Task.objects.get(pk=response.json()['id'])

    @staticmethod
    def cancellation_evaluation(**overrides):
        payload = {
            'decision': 'autorizar', 'reason': 'La actividad ya no es técnicamente necesaria',
            'work_assessment': 'Se revisó el trabajo ejecutado y se conserva el avance reportado',
            'evidence_assessment': 'Se revisaron las evidencias históricas disponibles',
            'dependency_assessment': 'Se identificaron dependencias y se conserva su seguimiento',
            'obligation_disposition': 'follow_up',
            'obligation_assessment': 'La obligación sigue pendiente y no se considera cumplida',
            'obligation_follow_up': 'L3 mantiene el seguimiento hasta su resolución autorizada',
            'commercial_impact': 'none',
            'commercial_assessment': 'No se identifican consecuencias comerciales nuevas',
            'evidence': 'Informe técnico T-07',
        }
        return {**payload, **overrides}

    def propose_cancellation(self, task, *, level='L4'):
        return self.api.post(
            f'/api/tasks/{task.id}/cancellation/proposal', headers=self.headers[level],
            json={'reason': 'Se propone retirar esta actividad',
                  'effects': 'Conservar trabajo y mantener seguimiento de la obligación',
                  'evidence': 'Informe de alcance vigente'},
        )

    def test_cancellation_proposal_evaluation_and_application_preserve_task_history_and_project(self):
        task = self.create_cancelable_task()
        dependency = self.create_cancelable_task()
        blocked = self.api.post(
            f'/api/tasks/{task.id}/block', headers=self.headers['L4'],
            json={'reason': 'Impedimento previo'},
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)
        project_status = self.project.status
        dependency_status = dependency.status
        initial_assignee = task.assignee_id
        prior_events = list(TaskEvent.objects.filter(task=task).values_list('event_type', flat=True))

        proposal = self.propose_cancellation(task)
        self.assertEqual(proposal.status_code, 200, proposal.text)
        self.assertEqual(proposal.json()['status'], 'Asignada')
        self.assertTrue(proposal.json()['actions']['can_propose_cancellation'])
        l3_view = self.api.get(f'/api/tasks/{task.id}', headers=self.headers['L3'])
        self.assertTrue(l3_view.json()['actions']['can_evaluate_cancellation'])
        self.assertEqual(list(TaskEvent.objects.filter(task=task).values_list('event_type', flat=True))[:-1], prior_events)
        proposal_event = TaskEvent.objects.filter(task=task, event_type='cancelacion_propuesta').get()
        self.assertEqual(proposal_event.reason, 'Se propone retirar esta actividad')
        self.assertIn('seguimiento de la obligación', proposal_event.result_text)

        evaluation = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'],
            json=self.cancellation_evaluation(),
        )
        self.assertEqual(evaluation.status_code, 200, evaluation.text)
        self.assertEqual(evaluation.json()['status'], 'Asignada')
        self.assertTrue(evaluation.json()['actions']['can_apply_cancellation'])
        eval_event = TaskEvent.objects.filter(task=task, event_type='cancelacion_autorizada').get()
        self.assertIn('L3 mantiene el seguimiento', eval_event.result_text)

        applied = self.api.post(
            f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
        )
        self.assertEqual(applied.status_code, 200, applied.text)
        task.refresh_from_db()
        dependency.refresh_from_db()
        self.assertEqual(task.status, 'Cancelada')
        self.assertEqual(task.assignee_id, initial_assignee)
        self.assertTrue(task.is_blocked)
        self.assertEqual(dependency.status, dependency_status)
        self.assertEqual([event.event_type for event in TaskEvent.objects.filter(task=task)][:len(prior_events)], prior_events)
        applied_event = TaskEvent.objects.filter(task=task, event_type='cancelacion_aplicada').get()
        self.assertEqual(applied_event.previous_status, 'Asignada')
        self.assertEqual(applied_event.new_status, 'Cancelada')
        l4_detail = self.api.get(f'/api/tasks/{task.id}', headers=self.headers['L4'])
        self.assertFalse(l4_detail.json()['actions']['can_propose_cancellation'])
        self.assertFalse(l4_detail.json()['actions']['can_unblock'])
        l5_detail = self.api.get(f'/api/tasks/{task.id}', headers=self.headers['L5'])
        self.assertFalse(l5_detail.json()['actions']['can_start'])
        after_apply = TaskEvent.objects.filter(task=task).count()
        self.assertEqual(self.api.post(
            f'/api/tasks/{task.id}/start', headers=self.headers['L5'],
        ).status_code, 409)
        self.assertEqual(self.api.post(
            f'/api/tasks/{task.id}/unblock', headers=self.headers['L4'],
            json={'reason': 'Levantar bloqueo'},
        ).status_code, 409)
        self.assertEqual(TaskEvent.objects.filter(task=task).count(), after_apply)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, project_status)

    def test_cancellation_denials_pending_obligations_and_finalized_state_do_not_apply(self):
        task = self.create_cancelable_task()
        self.assertEqual(self.propose_cancellation(task).status_code, 200)
        before_events = TaskEvent.objects.filter(task=task).count()
        pending = self.cancellation_evaluation(
            decision='pendiente', obligation_disposition='unresolved', obligation_follow_up='',
        )
        response = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'], json=pending,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'Asignada')
        self.assertTrue(response.json()['actions']['can_evaluate_cancellation'])
        unresolved_authorization = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'],
            json=self.cancellation_evaluation(obligation_disposition='unresolved', obligation_follow_up=''),
        )
        self.assertEqual(unresolved_authorization.status_code, 409)
        denied = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'],
            json=self.cancellation_evaluation(decision='denegar'),
        )
        self.assertEqual(denied.status_code, 200, denied.text)
        self.assertEqual(denied.json()['status'], 'Asignada')
        self.assertFalse(denied.json()['actions']['can_apply_cancellation'])
        apply_denied = self.api.post(
            f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
        )
        self.assertEqual(apply_denied.status_code, 409)
        task.refresh_from_db()
        self.assertEqual(task.status, 'Asignada')
        self.assertEqual(TaskEvent.objects.filter(task=task).count(), before_events + 2)

        finalized, _approval = self.make_finalized_task()
        finalized_proposal = self.propose_cancellation(finalized)
        self.assertEqual(finalized_proposal.status_code, 409)
        finalized.refresh_from_db()
        self.assertEqual(finalized.status, 'Finalizada')
        self.assertFalse(TaskEvent.objects.filter(task=finalized, event_type='cancelacion_propuesta').exists())

    def test_cancellation_scope_and_actor_levels_are_checked_by_api(self):
        task = self.create_cancelable_task()
        for level in ('L1', 'L2', 'L3', 'L5'):
            denied = self.propose_cancellation(task, level=level)
            self.assertEqual(denied.status_code, 403, f'{level}: {denied.text}')
        foreign_l4 = self.propose_cancellation(task, level='L4B')
        self.assertEqual(foreign_l4.status_code, 404)
        self.assertEqual(self.propose_cancellation(task).status_code, 200)
        for level in ('L1', 'L2', 'L4', 'L5'):
            denied = self.api.post(
                f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers[level],
                json=self.cancellation_evaluation(),
            )
            self.assertEqual(denied.status_code, 403, f'{level}: {denied.text}')
        foreign_l3 = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3B'],
            json=self.cancellation_evaluation(),
        )
        self.assertEqual(foreign_l3.status_code, 404)
        self.assertEqual(TaskEvent.objects.filter(task=task, event_type='cancelacion_autorizada').count(), 0)

    def test_new_commercial_consequences_require_l2_intervention_before_application(self):
        task = self.create_cancelable_task()
        self.assertEqual(self.propose_cancellation(task).status_code, 200)
        evaluation = self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'],
            json=self.cancellation_evaluation(commercial_impact='new_or_uncertain'),
        )
        self.assertEqual(evaluation.status_code, 200, evaluation.text)
        self.assertFalse(evaluation.json()['actions']['can_apply_cancellation'])
        context = self.api.get('/api/tasks/context', headers=self.headers['L2'])
        self.assertEqual(context.status_code, 200, context.text)
        self.assertEqual([item['task_id'] for item in context.json()['commercial_cancellations']], [task.id])
        premature = self.api.post(
            f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
        )
        self.assertEqual(premature.status_code, 409)
        invalid_l2 = self.api.post(
            f'/api/tasks/{task.id}/cancellation/commercial-review', headers=self.headers['L2B'],
            json={'decision': 'resuelta', 'reason': 'Revisión', 'evidence': 'Referencia'},
        )
        self.assertEqual(invalid_l2.status_code, 404)
        pending = self.api.post(
            f'/api/tasks/{task.id}/cancellation/commercial-review', headers=self.headers['L2'],
            json={'decision': 'pendiente', 'reason': 'Falta confirmar el ajuste', 'evidence': 'Contrato vigente'},
        )
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertEqual(self.api.post(
            f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
        ).status_code, 409)
        resolved = self.api.post(
            f'/api/tasks/{task.id}/cancellation/commercial-review', headers=self.headers['L2'],
            json={'decision': 'resuelta', 'reason': 'Condición comercial atendida', 'evidence': 'Autorización comercial C-14'},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(self.api.get('/api/tasks/context', headers=self.headers['L2']).json()['commercial_cancellations'], [])
        applied = self.api.post(
            f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
        )
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()['status'], 'Cancelada')
        event = TaskEvent.objects.get(task=task, event_type='revision_comercial_resuelta')
        self.assertEqual(event.actor_id, self.people['L2'].id)

    def test_failed_cancellation_application_rolls_back_state_and_history(self):
        task = self.create_cancelable_task()
        self.assertEqual(self.propose_cancellation(task).status_code, 200)
        self.assertEqual(self.api.post(
            f'/api/tasks/{task.id}/cancellation/evaluation', headers=self.headers['L3'],
            json=self.cancellation_evaluation(obligation_disposition='none', obligation_follow_up=''),
        ).status_code, 200)
        before_events = TaskEvent.objects.filter(task=task).count()
        with patch('api.routers.tasks.TaskEvent.objects.create', side_effect=IntegrityError):
            failed = self.api.post(
                f'/api/tasks/{task.id}/cancellation/apply', headers=self.headers['L3'],
            )
        self.assertEqual(failed.status_code, 409)
        task.refresh_from_db()
        self.assertEqual(task.status, 'Asignada')
        self.assertEqual(TaskEvent.objects.filter(task=task).count(), before_events)

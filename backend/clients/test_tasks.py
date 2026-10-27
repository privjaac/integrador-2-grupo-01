from django.test import TransactionTestCase
from django.utils import timezone
from fastapi.testclient import TestClient

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

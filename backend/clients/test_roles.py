from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from api.role_permissions import ROUTE_CAPABILITIES
from clients.models import Client, ClientChangeRequest, Collaborator, Role, RoleHistory, WebCatalog


class OrganizationalRoleTests(TransactionTestCase):
    def setUp(self):
        self.roles = {
            level: Role.objects.create(name=f'Base {level}', level=level)
            for level in ('L1', 'L2', 'L3', 'L4', 'L5')
        }
        self.admin = Collaborator.objects.create(
            first_name='Admin', last_name='Prueba', document_number='10000001',
            email='admin-role@example.com', username='admin-role',
            password_hash=hash_password('password-123'), role=self.roles['L1'],
            cupe='ELO-00000001',
        )
        self.manager = Collaborator.objects.create(
            first_name='Manager', last_name='Prueba', document_number='10000002',
            email='manager-role@example.com', username='manager-role',
            password_hash=hash_password('password-123'), role=self.roles['L2'],
            cupe='ELO-00000002',
        )
        self.api = TestClient(app)
        self.admin_token = self.login('admin-role')['access_token']
        self.manager_token = self.login('manager-role')['access_token']

    def login(self, username):
        response = self.api.post('/api/auth/login', json={'username': username, 'password': 'password-123'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def headers(self, token):
        return {'Authorization': f'Bearer {token}'}

    def create_org_role(self, **overrides):
        payload = {
            'name': 'Desarrollador de Soporte', 'level': 'L5',
            'description': 'Atención técnica organizada',
            'permissions': ['tasks.view', 'tasks.reportIncident'],
        }
        payload.update(overrides)
        return self.api.post('/api/roles/', headers=self.headers(self.admin_token), json=payload)

    def test_route_permission_map_covers_protected_api_operations(self):
        protected_routes = [
            route for route in app.routes
            if hasattr(route, 'path') and route.path.startswith('/api/')
            and not route.path.startswith('/api/auth/') and route.name != 'get_me'
        ]
        self.assertTrue(protected_routes)
        self.assertEqual(
            sorted(route.name for route in protected_routes if route.name not in ROUTE_CAPABILITIES),
            [],
        )

    def test_permission_subset_is_enforced_and_revocation_is_immediate(self):
        created = self.create_org_role()
        self.assertEqual(created.status_code, 201, created.text)
        role = Role.objects.get(pk=created.json()['id'])
        self.assertEqual(role.level, 'L5')
        self.assertEqual(role.permissions, ['tasks.view', 'tasks.reportIncident'])

        collaborator = Collaborator.objects.create(
            first_name='Soporte', last_name='Prueba', document_number='10000003',
            email='support-role@example.com', username='support-role',
            password_hash=hash_password('password-123'), role=role, cupe='ELO-00000003',
        )
        support_tokens = self.login('support-role')
        own = self.api.get('/api/users/me', headers=self.headers(support_tokens['access_token']))
        self.assertEqual(own.status_code, 200, own.text)
        self.assertEqual(set(own.json()['permissions']), {'tasks.view', 'tasks.reportIncident'})
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers(support_tokens['access_token'])).status_code, 200)
        self.assertEqual(self.api.get('/api/projects/', headers=self.headers(support_tokens['access_token'])).status_code, 403)

        reduced = self.api.put(
            f'/api/roles/{role.id}', headers=self.headers(self.admin_token),
            json={'permissions': []},
        )
        self.assertEqual(reduced.status_code, 200, reduced.text)
        self.assertEqual(self.api.get('/api/tasks/', headers=self.headers(support_tokens['access_token'])).status_code, 403)
        self.assertGreaterEqual(RoleHistory.objects.filter(role_id_snapshot=role.id).count(), 2)

        deactivated = self.api.put(
            f'/api/roles/{role.id}', headers=self.headers(self.admin_token),
            json={'is_active': False},
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertEqual(self.api.get('/api/users/me', headers=self.headers(support_tokens['access_token'])).status_code, 401)
        self.assertEqual(self.api.post('/api/auth/login', json={
            'username': 'support-role', 'password': 'password-123',
        }).status_code, 403)
        self.assertEqual(self.api.post('/api/auth/refresh', json={
            'refresh_token': support_tokens['refresh_token'],
        }).status_code, 401)
        self.assertTrue(Collaborator.objects.filter(pk=collaborator.pk, is_active=True).exists())

    def test_permission_escalation_duplicate_and_administration_are_denied(self):
        invalid = self.create_org_role(name='Rol fuera de nivel', permissions=['projects.create'])
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertFalse(Role.objects.filter(name='Rol fuera de nivel').exists())

        created = self.create_org_role()
        self.assertEqual(created.status_code, 201, created.text)
        duplicate = self.create_org_role()
        self.assertEqual(duplicate.status_code, 409)

        forbidden = self.api.post('/api/roles/', headers=self.headers(self.manager_token), json={
            'name': 'Manager role', 'level': 'L3', 'permissions': [],
        })
        self.assertEqual(forbidden.status_code, 403)

        base_l1 = self.roles['L1']
        forbidden_permissions = self.api.put(
            f'/api/roles/{base_l1.id}', headers=self.headers(self.admin_token),
            json={'permissions': []},
        )
        self.assertEqual(forbidden_permissions.status_code, 409)
        allowed_description = self.api.put(
            f'/api/roles/{base_l1.id}', headers=self.headers(self.admin_token),
            json={'description': 'Descripción administrativa actualizada'},
        )
        self.assertEqual(allowed_description.status_code, 200, allowed_description.text)

    def test_role_deletion_preserves_history_and_blocks_assigned_roles(self):
        created = self.create_org_role(name='Rol temporal', permissions=[])
        self.assertEqual(created.status_code, 201, created.text)
        role_id = created.json()['id']
        assigned = Collaborator.objects.create(
            first_name='Temporal', last_name='Prueba', document_number='10000004',
            email='temporary-role@example.com', username='temporary-role',
            password_hash=hash_password('password-123'), role_id=role_id,
            cupe='ELO-00000004',
        )
        blocked = self.api.delete(f'/api/roles/{role_id}', headers=self.headers(self.admin_token))
        self.assertEqual(blocked.status_code, 409)

        role = Role.objects.get(pk=role_id)
        role.collaborators.update(is_active=False)
        blocked_inactive = self.api.delete(f'/api/roles/{role_id}', headers=self.headers(self.admin_token))
        self.assertEqual(blocked_inactive.status_code, 409)

        unused = self.create_org_role(name='Rol sin asignaciones', permissions=[])
        self.assertEqual(unused.status_code, 201, unused.text)
        unused_id = unused.json()['id']
        removed = self.api.delete(f'/api/roles/{unused_id}', headers=self.headers(self.admin_token))
        self.assertEqual(removed.status_code, 200, removed.text)
        history = RoleHistory.objects.filter(role_id_snapshot=unused_id, action='deleted').first()
        self.assertIsNotNone(history)
        self.assertIsNone(history.role_id)

    def test_deactivation_resolution_requires_its_specific_permission(self):
        catalog = WebCatalog.objects.create(name='Prueba', base_price_rent=10, base_price_sale=100)
        client = Client.objects.create(
            name='Cliente de prueba', document_type='RUC', document_number='20100000001',
            web_type=catalog, plan='alquiler', status='desarrollo',
        )
        requested = self.api.post(
            f'/api/clients/{client.id}/deactivation-requests',
            headers=self.headers(self.admin_token), json={'reason': 'Solicitud de prueba'},
        )
        self.assertEqual(requested.status_code, 201, requested.text)
        request = ClientChangeRequest.objects.get(pk=requested.json()['id'])

        limited = self.create_org_role(
            name='L1 sin autoridad de baja', level='L1', permissions=['clients.resolveChange'],
        )
        self.assertEqual(limited.status_code, 201, limited.text)
        self.admin.role = Role.objects.get(pk=limited.json()['id'])
        self.admin.save(update_fields=['role'])
        limited_tokens = self.login('admin-role')
        denied = self.api.post(
            f'/api/clients/requests/{request.id}/resolve',
            headers=self.headers(limited_tokens['access_token']),
            json={'decision': 'aprobado', 'reason': 'Intento de prueba'},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        request.refresh_from_db()
        client.refresh_from_db()
        self.assertEqual(request.status, 'pendiente')
        self.assertEqual(client.status, 'desarrollo')

    def test_account_creation_rejects_inactive_role_without_partial_write(self):
        created = self.create_org_role(name='Rol que se desactivará', level='L3', permissions=[])
        self.assertEqual(created.status_code, 201, created.text)
        role_id = created.json()['id']
        inactive = self.api.put(
            f'/api/roles/{role_id}', headers=self.headers(self.admin_token),
            json={'is_active': False},
        )
        self.assertEqual(inactive.status_code, 200, inactive.text)

        response = self.api.post('/api/users/', headers=self.headers(self.admin_token), json={
            'first_name': 'Cuenta', 'last_name': 'SinRolActivo', 'document_type': 'DNI',
            'document_number': 'NEW-INACTIVE-ROLE', 'email': 'inactive-role@example.com',
            'city': 'Lima', 'username': 'inactive-role', 'password': 'test-password',
            'role_id': role_id,
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertFalse(Collaborator.objects.filter(username='inactive-role').exists())

    def test_task_context_requires_a_specific_task_capability(self):
        no_task_access = self.create_org_role(
            name='L2 sin operaciones de tareas', level='L2', permissions=[],
        )
        self.assertEqual(no_task_access.status_code, 201, no_task_access.text)
        self.manager.role = Role.objects.get(pk=no_task_access.json()['id'])
        self.manager.save(update_fields=['role'])
        no_access_token = self.login('manager-role')['access_token']
        denied = self.api.get('/api/tasks/context', headers=self.headers(no_access_token))
        self.assertEqual(denied.status_code, 403)

        coordination = self.api.put(
            f"/api/roles/{self.manager.role_id}", headers=self.headers(self.admin_token),
            json={'permissions': ['tasks.designate']},
        )
        self.assertEqual(coordination.status_code, 200, coordination.text)
        allowed = self.api.get('/api/tasks/context', headers=self.headers(no_access_token))
        self.assertEqual(allowed.status_code, 200, allowed.text)

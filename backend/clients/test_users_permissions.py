from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import Collaborator, Role


class CollaboratorPermissionApiTests(TransactionTestCase):
    def setUp(self):
        self.roles = {
            level: Role.objects.create(name=f'Permisos {level}', level=level)
            for level in ('L1', 'L2', 'L3', 'L4', 'L5')
        }
        self.actors = {
            level: self.make_collaborator(level, f'actor-{level}')
            for level in ('L1', 'L2', 'L3', 'L4', 'L5')
        }
        self.target_l1 = self.make_collaborator('L1', 'target-l1')
        self.target_l2 = self.make_collaborator('L2', 'target-l2')
        self.target_l3 = self.make_collaborator('L3', 'target-l3')
        self.target_l4 = self.make_collaborator('L4', 'target-l4')
        self.target_l5 = self.make_collaborator('L5', 'target-l5')
        self.api = TestClient(app)
        self.headers = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            response = self.api.post('/api/auth/login', json={
                'username': f'actor-{level}', 'password': 'test-password',
            })
            self.headers[level] = {'Authorization': f"Bearer {response.json()['access_token']}"}

    def make_collaborator(self, level, suffix):
        return Collaborator.objects.create(
            first_name='Actor', last_name=suffix,
            document_number=f'DOC-{suffix}', email=f'{suffix}@example.com',
            username=suffix, password_hash=hash_password('test-password'),
            role=self.roles[level],
        )

    def test_list_detail_and_creation_follow_functional_level(self):
        for level in ('L1', 'L2', 'L3', 'L4'):
            with self.subTest(list_level=level):
                self.assertEqual(self.api.get('/api/users/', headers=self.headers[level]).status_code, 200)
                self.assertEqual(self.api.get(f'/api/users/{self.target_l5.id}', headers=self.headers[level]).status_code, 200)
        self.assertEqual(self.api.get('/api/users/', headers=self.headers['L5']).status_code, 403)

        targets = {'L1': 'L1', 'L2': 'L3', 'L3': 'L4', 'L4': 'L5'}
        for actor_level, target_level in targets.items():
            with self.subTest(create_actor=actor_level, target=target_level):
                result = self.api.post('/api/users/', headers=self.headers[actor_level], json={
                    'first_name': 'Creado', 'last_name': target_level,
                    'document_type': 'DNI', 'document_number': f'NEW-{actor_level}-{target_level}',
                    'email': f'new-{actor_level}-{target_level}@example.com',
                    'city': 'Lima', 'username': f'new-{actor_level}-{target_level}',
                    'password': 'test-password', 'role_id': self.roles[target_level].id,
                })
                self.assertEqual(result.status_code, 201, result.text)

        forbidden = self.api.post('/api/users/', headers=self.headers['L2'], json={
            'first_name': 'No', 'last_name': 'L2', 'document_type': 'DNI',
            'document_number': 'NEW-L2-L2', 'email': 'new-l2-l2@example.com',
            'city': 'Lima', 'username': 'new-l2-l2', 'password': 'test-password',
            'role_id': self.roles['L2'].id,
        })
        self.assertEqual(forbidden.status_code, 403)

    def test_edit_and_activation_require_authorized_actor_and_target(self):
        cases = [
            ('L1', self.target_l1, 403), ('L1', self.actors['L1'], 403),
            ('L1', self.target_l2, 200),
            ('L2', self.target_l1, 403), ('L2', self.target_l2, 200),
            ('L2', self.target_l3, 200), ('L2', self.target_l4, 200),
            ('L3', self.target_l5, 403), ('L4', self.target_l5, 403),
            ('L5', self.target_l5, 403),
        ]
        for actor_level, target, expected in cases:
            with self.subTest(edit_actor=actor_level, target=target.username):
                response = self.api.put(
                    f'/api/users/{target.id}', headers=self.headers[actor_level],
                    json={'phone': '999111222'},
                )
                self.assertEqual(response.status_code, expected, response.text)

        for actor_level, target, expected in cases:
            with self.subTest(toggle_actor=actor_level, target=target.username):
                response = self.api.delete(f'/api/users/{target.id}', headers=self.headers[actor_level])
                self.assertEqual(response.status_code, expected, response.text)

    def test_authorized_peer_can_reactivate_without_profile_changes(self):
        self.target_l2.is_active = False
        self.target_l2.phone = '111222333'
        self.target_l2.save(update_fields=['is_active', 'phone'])

        response = self.api.put(
            f'/api/users/{self.target_l2.id}', headers=self.headers['L2'],
            json={'is_active': True},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.target_l2.refresh_from_db()
        self.assertTrue(self.target_l2.is_active)
        self.assertEqual(self.target_l2.phone, '111222333')

    def test_role_and_status_cannot_be_changed_through_profile_edit(self):
        changed_role = self.api.put(
            f'/api/users/{self.target_l3.id}', headers=self.headers['L1'],
            json={'role_id': self.roles['L5'].id},
        )
        changed_status = self.api.put(
            f'/api/users/{self.target_l3.id}', headers=self.headers['L1'],
            json={'is_active': False},
        )
        self.assertEqual(changed_role.status_code, 403)
        self.assertEqual(changed_status.status_code, 403)
        self.target_l3.refresh_from_db()
        self.assertEqual(self.target_l3.role.level, 'L3')
        self.assertTrue(self.target_l3.is_active)

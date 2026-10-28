from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import Collaborator, ElomuxPlatform, ElomuxPlatformEvent, Role


class ElomuxPlatformApiTests(TransactionTestCase):
    def setUp(self):
        self.tokens = {}
        self.roles = {}
        for index, level in enumerate(('L1', 'L2', 'L3', 'L4', 'L5'), start=1):
            role = Role.objects.create(name=f'Platform test {level}', level=level)
            self.roles[level] = role
            Collaborator.objects.create(
                first_name='Platform', last_name=level, document_number=f'PLATFORM-{index}',
                email=f'platform-{level}@example.test', username=f'platform-{level}',
                password_hash=hash_password('platform-password'), role=role,
            )
        self.api = TestClient(app)
        for level in self.roles:
            response = self.api.post('/api/auth/login', json={
                'username': f'platform-{level}', 'password': 'platform-password',
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.tokens[level] = response.json()['access_token']

    def headers(self, level):
        return {'Authorization': f'Bearer {self.tokens[level]}'}

    def test_l1_l2_manage_and_l1_l2_l3_read_with_immutable_history(self):
        created = self.api.post('/api/elomux-platforms/', headers=self.headers('L1'), json={
            'name': 'TikTok', 'url': 'https://tiktok.com/elomux', 'is_active': True,
        })
        self.assertEqual(created.status_code, 201, created.text)
        platform_id = created.json()['id']
        event = ElomuxPlatformEvent.objects.get(platform_id=platform_id)
        self.assertEqual(event.actor.role.level, 'L1')
        self.assertEqual(event.action, 'created')
        self.assertEqual(event.after['url'], 'https://tiktok.com/elomux')

        for level in ('L1', 'L2', 'L3'):
            listed = self.api.get('/api/elomux-platforms/', headers=self.headers(level))
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual(listed.json()[0]['name'], 'TikTok')

        updated = self.api.put(f'/api/elomux-platforms/{platform_id}', headers=self.headers('L2'), json={
            'url': 'https://www.tiktok.com/elomux', 'is_active': False,
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertFalse(updated.json()['is_active'])
        update_event = ElomuxPlatformEvent.objects.get(action='updated')
        self.assertEqual(update_event.actor.role.level, 'L2')
        self.assertTrue(update_event.before['is_active'])
        self.assertFalse(update_event.after['is_active'])
        self.assertEqual(ElomuxPlatform.objects.count(), 1)

    def test_tl_is_read_only_and_l4_l5_cannot_read(self):
        self.assertEqual(self.api.post('/api/elomux-platforms/', headers=self.headers('L3'), json={
            'name': 'Instagram', 'url': 'https://instagram.com/elomux',
        }).status_code, 403)
        for level in ('L4', 'L5'):
            self.assertEqual(self.api.get('/api/elomux-platforms/', headers=self.headers(level)).status_code, 403)

    def test_duplicate_name_is_case_insensitive_and_does_not_create_partial_history(self):
        first = self.api.post('/api/elomux-platforms/', headers=self.headers('L2'), json={
            'name': 'TikTok', 'url': 'https://tiktok.com',
        })
        self.assertEqual(first.status_code, 201, first.text)
        duplicate = self.api.post('/api/elomux-platforms/', headers=self.headers('L1'), json={
            'name': 'tIkToK', 'url': 'https://example.com',
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(ElomuxPlatform.objects.count(), 1)
        self.assertEqual(ElomuxPlatformEvent.objects.count(), 1)

    def test_invalid_url_unknown_platform_and_custom_permission_are_denied(self):
        invalid = self.api.post('/api/elomux-platforms/', headers=self.headers('L1'), json={
            'name': 'Bad URL', 'url': 'not a URL',
        })
        self.assertEqual(invalid.status_code, 422)

        unknown = self.api.put('/api/elomux-platforms/987654', headers=self.headers('L2'), json={
            'is_active': False,
        })
        self.assertEqual(unknown.status_code, 404)

        self.roles['L2'].permissions = ['platforms.view']
        self.roles['L2'].save(update_fields=['permissions'])
        denied = self.api.post('/api/elomux-platforms/', headers=self.headers('L2'), json={
            'name': 'LinkedIn', 'url': 'https://linkedin.com',
        })
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(ElomuxPlatform.objects.exists())
        self.assertFalse(ElomuxPlatformEvent.objects.exists())

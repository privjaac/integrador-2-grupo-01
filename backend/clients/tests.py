from django.test import TransactionTestCase
from django.core.management import call_command
from django.conf import settings
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.routers.auth import hash_password, verify_password
from clients.models import Client, Collaborator, Role, WebCatalog, WebFeature


class ApiContractTests(TransactionTestCase):
    def setUp(self):
        role = Role.objects.create(name='Superadmin', level='L1')
        self.admin = Collaborator.objects.create(
            first_name='Admin',
            last_name='Prueba',
            document_number='12345678',
            email='admin@example.com',
            username='admin',
            password_hash=hash_password('test-password'),
            role=role,
            cupe='ELO-00000000',
        )
        self.web_type = WebCatalog.objects.create(
            name='Landing Page', base_price_rent=49, base_price_sale=299
        )
        self.feature = WebFeature.objects.create(name='Chat', extra_price=20)
        self.api = TestClient(app)

    def login(self):
        response = self.api.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'test-password'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_login_identity_and_token_scope(self):
        tokens = self.login()
        response = self.api.get(
            '/api/users/me',
            headers={'Authorization': f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['role'], 'L1')
        self.assertNotIn('password_hash', response.json())

        refresh_as_access = self.api.get(
            '/api/users/me',
            headers={'Authorization': f"Bearer {tokens['refresh_token']}"},
        )
        self.assertEqual(refresh_as_access.status_code, 401)

        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        inactive = self.api.get(
            '/api/users/me',
            headers={'Authorization': f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(inactive.status_code, 401)

    def test_collaborator_list_returns_users_and_supports_filters(self):
        token = self.login()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        listing = self.api.get('/api/users/', headers=headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(len(listing.json()), 1)
        self.assertEqual(listing.json()[0]['username'], 'admin')
        self.assertNotIn('password_hash', listing.json()[0])

        filtered = self.api.get(
            '/api/users/', headers=headers,
            params={'is_active': True, 'role_id': self.admin.role_id, 'search': 'Admin'},
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(len(filtered.json()), 1)

        missing = self.api.get(
            '/api/users/', headers=headers, params={'search': 'nadie'},
        )
        self.assertEqual(missing.status_code, 200, missing.text)
        self.assertEqual(missing.json(), [])

    def test_client_features_and_prices_are_persisted(self):
        token = self.login()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        response = self.api.post(
            '/api/clients/',
            headers=headers,
            json={
                'name': 'Cliente de prueba',
                'document_type': 'RUC',
                'document_number': '20123456789',
                'email': 'cliente@example.com',
                'web_type_id': self.web_type.id,
                'plan': 'alquiler',
                'feature_ids': [self.feature.id],
                'base_price': 1,
                'total_price': 1,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['total_price'], 69)
        self.assertEqual(response.json()['features'], [
            {'id': self.feature.id, 'name': 'Chat', 'extra_price': 20.0}
        ])
        client_id = response.json()['id']

        listing = self.api.get('/api/clients/', headers=headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()[0]['email'], 'cliente@example.com')
        self.assertEqual(listing.json()[0]['features'][0]['name'], 'Chat')

        update = self.api.put(
            f'/api/clients/{client_id}',
            headers=headers,
            json={'feature_ids': [], 'plan': 'venta'},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()['total_price'], 299)
        self.assertEqual(update.json()['features'], [])
        self.assertEqual(Client.objects.get(id=client_id).plan, 'venta')

    def test_role_edit_is_superadmin_only_and_levels_stay_fixed(self):
        editor_role = Role.objects.create(name='Scrum Master', level='L2')
        editor = Collaborator.objects.create(
            first_name='Editor', last_name='Prueba',
            document_number='87654321', email='editor@example.com',
            username='editor', password_hash=hash_password('editor-password'),
            role=editor_role,
        )
        admin_token = self.login()['access_token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}
        change = self.api.put(
            f'/api/roles/{editor_role.id}', headers=admin_headers,
            json={'name': 'Coordinador', 'description': 'Coordina el equipo'},
        )
        self.assertEqual(change.status_code, 200, change.text)
        self.assertEqual(change.json()['level'], 'L2')
        self.assertEqual(change.json()['description'], 'Coordina el equipo')

        editor_login = self.api.post(
            '/api/auth/login',
            json={'username': editor.username, 'password': 'editor-password'},
        )
        editor_headers = {
            'Authorization': f"Bearer {editor_login.json()['access_token']}"
        }
        forbidden = self.api.put(
            f'/api/roles/{editor_role.id}', headers=editor_headers,
            json={'name': 'Otro'},
        )
        self.assertEqual(forbidden.status_code, 403)
        elevation = self.api.post(
            '/api/users/', headers=editor_headers,
            json={
                'first_name': 'Nuevo', 'last_name': 'Admin',
                'document_type': 'DNI', 'document_number': '11111111',
                'email': 'nuevo@example.com', 'city': 'Lima',
                'username': 'nuevo', 'password': 'test-password',
                'role_id': self.admin.role_id,
            },
        )
        self.assertEqual(elevation.status_code, 403)

    def test_cupe_change_is_recorded_and_filtered(self):
        client = Client.objects.create(
            cupe='CLI-01007918', name='Cliente CUPE',
            document_number='20987654321', web_type=self.web_type,
        )
        token = self.login()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        candidate = self.api.get('/api/cupe-log/next-client', headers=headers)
        self.assertEqual(candidate.status_code, 200, candidate.text)
        new_cupe = candidate.json()['next_cupe']
        change = self.api.post(
            '/api/cupe-log/', headers=headers,
            json={
                'entity_type': 'client', 'entity_id': client.id,
                'new_cupe': new_cupe, 'reason': 'correccion_administrativa',
                'observations': 'Corrección de prueba',
            },
        )
        self.assertEqual(change.status_code, 201, change.text)
        client.refresh_from_db()
        self.assertEqual(client.cupe, new_cupe)

        history = self.api.get(
            '/api/cupe-log/', headers=headers,
            params={'entity_type': 'client', 'entity_id': client.id},
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]['observations'], 'Corrección de prueba')

    def test_new_user_password_is_bcrypt_hash_and_never_returned(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        role = Role.objects.create(name='Developer', level='L5')
        response = self.api.post('/api/users/', headers=headers, json={
            'first_name': 'Ana', 'last_name': 'Prueba',
            'document_type': 'DNI', 'document_number': '87654321',
            'email': 'ana@example.com', 'city': 'Lima',
            'username': 'ana', 'password': 'ClaveSegura123!', 'role_id': role.id,
        })
        self.assertEqual(response.status_code, 201, response.text)
        stored = Collaborator.objects.get(username='ana')
        self.assertTrue(stored.password_hash.startswith('$2'))
        self.assertEqual(len(stored.password_hash), 60)
        self.assertNotEqual(stored.password_hash, 'ClaveSegura123!')
        self.assertTrue(verify_password('ClaveSegura123!', stored.password_hash))
        self.assertNotIn('password_hash', response.json())
        self.assertNotIn('ClaveSegura123!', response.text)

    def test_xss_payload_is_rejected_before_persistence(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        for malicious_name in ("<script>alert('XSS')</script>",
                               '&lt;script&gt;alert(1)&lt;/script&gt;',
                               '&amp;lt;script&amp;gt;alert(1)&amp;lt;/script&amp;gt;'):
            response = self.api.post('/api/clients/', headers=headers, json={
                'name': malicious_name, 'document_type': 'RUC',
                'document_number': '20123456789',
                'web_type_id': self.web_type.id, 'plan': 'alquiler',
            })
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn('<script>', response.text)
        self.assertEqual(Client.objects.count(), 0)

        user_attempt = self.api.post('/api/users/', headers=headers, json={
            'first_name': '<img src=x onerror=alert(1)>',
            'last_name': 'Prueba', 'document_type': 'DNI',
            'document_number': '87654321', 'email': 'xss@example.com',
            'city': 'Lima', 'username': 'xss', 'password': 'test-password',
            'role_id': self.admin.role_id,
        })
        self.assertEqual(user_attempt.status_code, 422)
        self.assertFalse(Collaborator.objects.filter(username='xss').exists())

        blank_name = self.api.post('/api/clients/', headers=headers, json={
            'name': '   ', 'document_type': 'RUC',
            'document_number': '20123456789',
            'web_type_id': self.web_type.id, 'plan': 'alquiler',
        })
        self.assertEqual(blank_name.status_code, 422)

        null_password = self.api.put(
            f'/api/users/{self.admin.id}', headers=headers, json={'password': None},
        )
        self.assertEqual(null_password.status_code, 422)

    def test_json_output_escapes_legacy_html_data(self):
        self.web_type.name = '<b>Nombre heredado</b> & más'
        self.web_type.save(update_fields=['name'])
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        response = self.api.get('/api/web-types/', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('\\u003cb\\u003e', response.text)
        self.assertNotIn('<b>', response.text)
        self.assertEqual(response.json()[0]['name'], '<b>Nombre heredado</b> & más')

    def test_cors_allows_frontend_and_denies_unlisted_origin(self):
        self.assertTrue(settings.CORS_ALLOWED_ORIGINS)
        allowed_origin = settings.CORS_ALLOWED_ORIGINS[0]
        for origin, expected in ((allowed_origin, allowed_origin),
                                 ('https://evil.example', None)):
            response = self.api.options('/api/clients/', headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type',
            })
            self.assertEqual(response.headers.get('access-control-allow-origin'), expected)
            self.assertNotEqual(response.headers.get('access-control-allow-origin'), '*')
            self.assertEqual(response.status_code, 200 if expected else 400)

    def test_authorization_and_orm_query_resist_injection(self):
        self.assertEqual(self.api.get('/api/users/').status_code, 401)
        self.assertEqual(self.api.get('/api/users/', headers={
            'Authorization': 'Bearer invalid-token',
        }).status_code, 401)
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        self.assertEqual(self.api.get('/api/users/', headers=headers).status_code, 200)
        injection = self.api.get('/api/users/', headers=headers, params={
            'search': "' OR 1=1 --",
        })
        self.assertEqual(injection.status_code, 200, injection.text)
        self.assertEqual(injection.json(), [])
        self.assertEqual(Collaborator.objects.count(), 1)


class BootstrapTests(TransactionTestCase):
    def test_first_admin_can_log_in(self):
        with patch.dict('os.environ', {'ELISA_BOOTSTRAP_PASSWORD': 'initial-password'}):
            call_command(
                'bootstrap_elisa', username='first-admin',
                email='first@example.com', document_number='12345678',
                verbosity=0,
            )
        self.assertEqual(Role.objects.count(), 5)
        response = TestClient(app).post(
            '/api/auth/login',
            json={'username': 'first-admin', 'password': 'initial-password'},
        )
        self.assertEqual(response.status_code, 200, response.text)

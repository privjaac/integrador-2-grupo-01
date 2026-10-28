from django.test import TransactionTestCase
from django.core.management import call_command
from django.conf import settings
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from api.routers.auth import hash_password, verify_password
from clients.models import Client, ClientChangeRequest, ClientHistory, Collaborator, Role, WebCatalog, WebFeature


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

    def test_refresh_token_returns_new_access_token(self):
        tokens = self.login()
        response = self.api.post(
            '/api/auth/refresh',
            json={'refresh_token': tokens['refresh_token']},
        )
        self.assertEqual(response.status_code, 200, response.text)
        refreshed = response.json()
        self.assertIsInstance(refreshed['access_token'], str)
        self.assertTrue(refreshed['access_token'])
        self.assertEqual(refreshed['refresh_token'], tokens['refresh_token'])
        self.assertEqual(refreshed['token_type'], 'bearer')

    def test_access_token_cannot_be_used_as_refresh_token(self):
        tokens = self.login()
        response = self.api.post(
            '/api/auth/refresh',
            json={'refresh_token': tokens['access_token']},
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_invalid_refresh_token_is_rejected(self):
        response = self.api.post(
            '/api/auth/refresh',
            json={'refresh_token': 'invalid-refresh-token'},
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_logout_returns_success_message(self):
        response = self.api.post('/api/auth/logout')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {'message': 'Sesión cerrada correctamente'},
        )

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
        self.assertEqual(update.status_code, 409, update.text)
        self.assertEqual(Client.objects.get(id=client_id).plan, 'alquiler')

    def test_client_change_request_requires_approval_and_records_history(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        created = self.api.post('/api/clients/', headers=headers, json={
            'name': 'Cliente aprobación', 'document_type': 'RUC',
            'document_number': '20123456780', 'email': 'old@example.com',
            'web_type_id': self.web_type.id, 'plan': 'alquiler',
        })
        client_id = created.json()['id']
        requested = self.api.post(f'/api/clients/{client_id}/change-requests', headers=headers,
                                  json={'changes': {'email': 'new@example.com'}, 'reason': 'Actualizar contacto'})
        self.assertEqual(requested.status_code, 201, requested.text)
        self.assertEqual(Client.objects.get(pk=client_id).email, 'old@example.com')
        history = self.api.get(f'/api/clients/{client_id}/history', headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual([event['event_type'] for event in history.json()], ['modificacion_solicitada', 'cliente_creado'])
        queue = self.api.get('/api/clients/requests/pending', headers=headers)
        self.assertEqual(queue.status_code, 200, queue.text)
        resolved = self.api.post(f"/api/clients/requests/{requested.json()['id']}/resolve", headers=headers,
                                 json={'decision': 'aprobado', 'reason': 'Verificado'})
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(Client.objects.get(pk=client_id).email, 'new@example.com')
        request_row = ClientChangeRequest.objects.get(pk=requested.json()['id'])
        self.assertEqual(request_row.status, 'aprobado')
        self.assertEqual(request_row.requester_id, self.admin.id)
        self.assertEqual(request_row.resolved_by_id, self.admin.id)
        self.assertIsNotNone(request_row.resolved_at)
        applied_event = ClientHistory.objects.get(request=request_row, event_type='modificacion_aprobada')
        self.assertEqual(applied_event.actor_id, self.admin.id)
        self.assertEqual(applied_event.before_data['email'], 'old@example.com')
        self.assertEqual(applied_event.after_data['email'], 'new@example.com')

    def test_client_deactivation_is_request_only_and_l1_approval_is_required(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        created = self.api.post('/api/clients/', headers=headers, json={
            'name': 'Cliente baja', 'document_type': 'RUC', 'document_number': '20123456781',
            'email': 'baja@example.com', 'web_type_id': self.web_type.id, 'plan': 'alquiler',
        })
        client_id = created.json()['id']
        cannot_directly_set_inactive = self.api.post(
            f'/api/clients/{client_id}/change-requests', headers=headers,
            json={'changes': {'status': 'inactivo'}, 'reason': 'Intento directo'},
        )
        self.assertEqual(cannot_directly_set_inactive.status_code, 409)
        self.assertEqual(self.api.delete(f'/api/clients/{client_id}', headers=headers).status_code, 409)
        request = self.api.post(f'/api/clients/{client_id}/deactivation-requests', headers=headers,
                                json={'reason': 'Cierre solicitado'})
        self.assertEqual(request.status_code, 201, request.text)
        self.assertNotEqual(Client.objects.get(pk=client_id).status, 'inactivo')
        resolved = self.api.post(f"/api/clients/requests/{request.json()['id']}/resolve", headers=headers,
                                 json={'decision': 'aprobado', 'reason': 'Aprobado'})
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(Client.objects.get(pk=client_id).status, 'inactivo')
        self.assertEqual(self.api.post(f'/api/clients/{client_id}/change-requests', headers=headers,
                                       json={'changes': {'status': 'activo'}, 'reason': 'Reactivar'}).status_code, 409)

    def test_l2_cannot_approve_deactivation(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        created = self.api.post('/api/clients/', headers=headers, json={
            'name': 'Cliente autorización L1', 'document_type': 'RUC', 'document_number': '20123456782',
            'email': 'auth@example.com', 'web_type_id': self.web_type.id, 'plan': 'alquiler',
        })
        req = self.api.post(f"/api/clients/{created.json()['id']}/deactivation-requests", headers=headers,
                            json={'reason': 'Baja solicitada'})
        role = Role.objects.create(name='Scrum Master', level='L2')
        collaborator = Collaborator.objects.create(
            first_name='SM', last_name='Prueba', document_number='55555555',
            email='sm@example.com', username='sm', password_hash=hash_password('sm-password'), role=role,
        )
        token_response = self.api.post('/api/auth/login', json={'username': collaborator.username, 'password': 'sm-password'})
        sm_headers = {'Authorization': f"Bearer {token_response.json()['access_token']}"}
        denied = self.api.post(f"/api/clients/requests/{req.json()['id']}/resolve", headers=sm_headers,
                               json={'decision': 'aprobado', 'reason': 'No competente'})
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertEqual(Client.objects.get(pk=created.json()['id']).status, 'desarrollo')

    def test_rejection_and_stale_approval_preserve_client_and_request_history(self):
        headers = {'Authorization': f"Bearer {self.login()['access_token']}"}
        created = self.api.post('/api/clients/', headers=headers, json={
            'name': 'Cliente historial', 'document_type': 'RUC', 'document_number': '20123456783',
            'email': 'before@example.com', 'web_type_id': self.web_type.id, 'plan': 'alquiler',
        })
        client_id = created.json()['id']
        rejected_request = self.api.post(f'/api/clients/{client_id}/change-requests', headers=headers,
                                         json={'changes': {'email': 'reject@example.com'}, 'reason': 'Cambio propuesto'})
        rejected = self.api.post(f"/api/clients/requests/{rejected_request.json()['id']}/resolve", headers=headers,
                                 json={'decision': 'rechazado', 'reason': 'No procede'})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(Client.objects.get(pk=client_id).email, 'before@example.com')

        stale_request = self.api.post(f'/api/clients/{client_id}/change-requests', headers=headers,
                                      json={'changes': {'email': 'stale@example.com'}, 'reason': 'Otra propuesta'})
        Client.objects.filter(pk=client_id).update(email='intervening@example.com')
        stale = self.api.post(f"/api/clients/requests/{stale_request.json()['id']}/resolve", headers=headers,
                              json={'decision': 'aprobado', 'reason': 'Revisar'})
        self.assertEqual(stale.status_code, 409, stale.text)
        request_row = ClientChangeRequest.objects.get(pk=stale_request.json()['id'])
        self.assertEqual(request_row.status, 'pendiente')
        self.assertEqual(Client.objects.get(pk=client_id).email, 'intervening@example.com')
        event_types = set(ClientHistory.objects.filter(client_id=client_id).values_list('event_type', flat=True))
        self.assertIn('modificacion_rechazada', event_types)
        self.assertNotIn('modificacion_aprobada', event_types)

    def test_crm_read_and_write_scope_excludes_l4(self):
        role = Role.objects.create(name='Líder', level='L4')
        collaborator = Collaborator.objects.create(
            first_name='Lider', last_name='Prueba', document_number='66666666',
            email='leader@example.com', username='leader', password_hash=hash_password('leader-password'), role=role,
        )
        token = self.api.post('/api/auth/login', json={
            'username': collaborator.username, 'password': 'leader-password',
        }).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        for path in ('/api/clients/', '/api/clients/1', '/api/clients/1/history'):
            self.assertEqual(self.api.get(path, headers=headers).status_code, 403)
        self.assertEqual(self.api.post('/api/clients/', headers=headers, json={
            'name': 'No permitido', 'document_type': 'RUC', 'document_number': '20999999999',
            'email': 'denied@example.com', 'web_type_id': self.web_type.id, 'plan': 'alquiler',
        }).status_code, 403)

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

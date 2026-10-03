from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import Client, Collaborator, Role, WebCatalog


class SchemaValidationRegressionTests(TransactionTestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(name='Superadmin', level='L1')
        self.worker_role = Role.objects.create(name='Developer', level='L5')
        self.admin = Collaborator.objects.create(
            first_name='Admin',
            last_name='Prueba',
            document_number='12345678',
            email='admin@example.com',
            username='admin',
            password_hash=hash_password('test-password'),
            role=self.admin_role,
            cupe='ELO-00000000',
        )
        self.web_type = WebCatalog.objects.create(
            name='Landing Page',
            base_price_rent='49.00',
            base_price_sale='299.00',
        )
        self.api = TestClient(app)
        login = self.api.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'test-password'},
        )
        self.headers = {
            'Authorization': f"Bearer {login.json()['access_token']}"
        }

    def client_payload(self, **overrides):
        payload = {
            'name': 'Cliente válido',
            'document_type': 'RUC',
            'document_number': '20123456789',
            'phone': '999999999',
            'web_type_id': self.web_type.id,
            'plan': 'alquiler',
            'status': 'desarrollo',
        }
        payload.update(overrides)
        return payload

    def collaborator_payload(self, **overrides):
        payload = {
            'first_name': 'Ana',
            'last_name': 'Prueba',
            'document_type': 'DNI',
            'document_number': '87654321',
            'email': 'ana@example.com',
            'phone': '999999999',
            'city': 'Lima',
            'username': 'ana-prueba',
            'password': 'ClaveSegura123!',
            'role_id': self.worker_role.id,
            'area': 'Desarrollo',
        }
        payload.update(overrides)
        return payload

    def test_client_document_number_boundary(self):
        accepted = self.api.post(
            '/api/clients/',
            headers=self.headers,
            json=self.client_payload(document_number='1' * 20),
        )
        self.assertEqual(accepted.status_code, 201, accepted.text)

        rejected = self.api.post(
            '/api/clients/',
            headers=self.headers,
            json=self.client_payload(document_number='2' * 21),
        )
        self.assertEqual(rejected.status_code, 422, rejected.text)

    def test_client_invalid_strings_and_choices_are_422(self):
        cases = {
            'name': {'name': 'N' * 201},
            'phone': {'phone': '9' * 21},
            'document_type': {'document_type': 'OTRO'},
            'plan': {'plan': 'semanal'},
            'status': {'status': 'desconocido'},
        }
        for label, values in cases.items():
            with self.subTest(label=label):
                response = self.api.post(
                    '/api/clients/',
                    headers=self.headers,
                    json=self.client_payload(**values),
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_client_update_rejects_explicit_null_for_required_fields(self):
        client = Client.objects.create(
            name='Cliente existente',
            document_type='RUC',
            document_number='20999999991',
            web_type=self.web_type,
            plan='alquiler',
            status='desarrollo',
        )
        for field in ('name', 'document_type', 'document_number', 'plan', 'status'):
            with self.subTest(field=field):
                response = self.api.put(
                    f'/api/clients/{client.id}',
                    headers=self.headers,
                    json={field: None},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_collaborator_username_boundary(self):
        accepted = self.api.post(
            '/api/users/',
            headers=self.headers,
            json=self.collaborator_payload(username='u' * 50),
        )
        self.assertEqual(accepted.status_code, 201, accepted.text)

        rejected = self.api.post(
            '/api/users/',
            headers=self.headers,
            json=self.collaborator_payload(
                username='u' * 51,
                document_number='87654322',
                email='ana2@example.com',
            ),
        )
        self.assertEqual(rejected.status_code, 422, rejected.text)

    def test_collaborator_invalid_fields_are_422(self):
        cases = {
            'document_number': {'document_number': '1' * 21},
            'phone': {'phone': '9' * 21},
            'city_length': {'city': 'C' * 51},
            'city_choice': {'city': 'Tacna'},
            'document_type': {'document_type': 'OTRO'},
        }
        for label, values in cases.items():
            with self.subTest(label=label):
                response = self.api.post(
                    '/api/users/',
                    headers=self.headers,
                    json=self.collaborator_payload(**values),
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_collaborator_update_rejects_null_required_fields(self):
        for field in (
            'first_name', 'last_name', 'document_type', 'document_number',
            'email', 'city', 'username',
        ):
            with self.subTest(field=field):
                response = self.api.put(
                    f'/api/users/{self.admin.id}',
                    headers=self.headers,
                    json={field: None},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_catalog_role_and_feature_reject_invalid_values(self):
        editor_role = Role.objects.create(name='Scrum Master', level='L2')
        requests = (
            ('role name', 'put', f'/api/roles/{editor_role.id}', {'name': 'R' * 51}),
            ('role null', 'put', f'/api/roles/{editor_role.id}', {'name': None}),
            ('catalog name', 'post', '/api/web-types/', {
                'name': 'W' * 101,
                'base_price_rent': '49.00',
                'base_price_sale': '299.00',
            }),
            ('catalog null', 'put', f'/api/web-types/{self.web_type.id}', {
                'base_price_rent': None,
            }),
            ('feature name', 'post', '/api/web-features/', {
                'name': 'F' * 101,
                'extra_price': '10.00',
            }),
        )
        for label, method, url, payload in requests:
            with self.subTest(label=label):
                response = getattr(self.api, method)(
                    url, headers=self.headers, json=payload,
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_money_validation_covers_valid_and_invalid_decimal_values(self):
        valid = self.api.post(
            '/api/web-features/',
            headers=self.headers,
            json={'name': 'Precio válido', 'extra_price': '999999.99'},
        )
        self.assertEqual(valid.status_code, 201, valid.text)

        for label, value in (
            ('overflow', '1000000.00'),
            ('precision', '10.001'),
            ('nan', 'NaN'),
            ('infinity', 'Infinity'),
        ):
            with self.subTest(label=label):
                response = self.api.post(
                    '/api/web-features/',
                    headers=self.headers,
                    json={'name': f'Precio {label}', 'extra_price': value},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_client_update_duplicate_document_is_controlled(self):
        first = Client.objects.create(
            name='Primero', document_type='RUC', document_number='20111111111',
            web_type=self.web_type, plan='alquiler', status='desarrollo',
        )
        second = Client.objects.create(
            name='Segundo', document_type='RUC', document_number='20222222222',
            web_type=self.web_type, plan='alquiler', status='desarrollo',
        )
        response = self.api.put(
            f'/api/clients/{second.id}',
            headers=self.headers,
            json={'document_number': first.document_number},
        )
        self.assertEqual(response.status_code, 400, response.text)


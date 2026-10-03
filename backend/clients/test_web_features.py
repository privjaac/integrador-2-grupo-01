from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import Collaborator, Role, WebCatalog, WebFeature


class WebFeatureWebTypeRegressionTests(TransactionTestCase):
    def setUp(self):
        role = Role.objects.create(name='Superadmin', level='L1')
        Collaborator.objects.create(
            first_name='Admin',
            last_name='Prueba',
            document_number='12345678',
            email='admin@example.com',
            username='admin',
            password_hash=hash_password('test-password'),
            role=role,
        )
        self.type_a = WebCatalog.objects.create(
            name='Tipo A', base_price_rent='49.00', base_price_sale='299.00',
        )
        self.type_b = WebCatalog.objects.create(
            name='Tipo B', base_price_rent='59.00', base_price_sale='399.00',
        )
        self.type_c = WebCatalog.objects.create(
            name='Tipo C', base_price_rent='69.00', base_price_sale='499.00',
        )
        self.api = TestClient(app)
        login = self.api.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'test-password'},
        )
        self.headers = {
            'Authorization': f"Bearer {login.json()['access_token']}"
        }

    def create_feature(self, name, web_type_ids):
        response = self.api.post(
            '/api/web-features/',
            headers=self.headers,
            json={
                'name': name,
                'extra_price': '20.00',
                'web_type_ids': web_type_ids,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_and_response_preserve_optional_many_to_many(self):
        global_feature = self.create_feature('Global', [])
        one_type = self.create_feature('Sólo A', [self.type_a.id])
        two_types = self.create_feature(
            'A y B', [self.type_a.id, self.type_b.id],
        )

        self.assertEqual(global_feature['web_type_ids'], [])
        self.assertEqual(one_type['web_type_ids'], [self.type_a.id])
        self.assertEqual(
            set(two_types['web_type_ids']), {self.type_a.id, self.type_b.id},
        )
        self.assertEqual(
            set(WebFeature.objects.get(id=two_types['id']).web_types.values_list(
                'id', flat=True,
            )),
            {self.type_a.id, self.type_b.id},
        )

    def test_filter_returns_global_and_matching_features_only(self):
        self.create_feature('Global', [])
        self.create_feature('Sólo A', [self.type_a.id])
        self.create_feature('A y B', [self.type_a.id, self.type_b.id])

        expected = {
            self.type_a.id: {'Global', 'Sólo A', 'A y B'},
            self.type_b.id: {'Global', 'A y B'},
            self.type_c.id: {'Global'},
        }
        for web_type_id, names in expected.items():
            with self.subTest(web_type_id=web_type_id):
                response = self.api.get(
                    '/api/web-features/',
                    headers=self.headers,
                    params={'web_type_id': web_type_id},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual({item['name'] for item in response.json()}, names)

        all_features = self.api.get(
            '/api/web-features/', headers=self.headers,
        )
        self.assertEqual(len(all_features.json()), 3)

    def test_update_can_change_associations_and_return_to_global(self):
        feature = self.create_feature('Editable', [self.type_a.id])
        changed = self.api.put(
            f"/api/web-features/{feature['id']}",
            headers=self.headers,
            json={'web_type_ids': [self.type_b.id, self.type_c.id]},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(
            set(changed.json()['web_type_ids']), {self.type_b.id, self.type_c.id},
        )

        globalized = self.api.put(
            f"/api/web-features/{feature['id']}",
            headers=self.headers,
            json={'web_type_ids': []},
        )
        self.assertEqual(globalized.status_code, 200, globalized.text)
        self.assertEqual(globalized.json()['web_type_ids'], [])

    def test_unknown_or_duplicate_web_type_ids_are_rejected(self):
        unknown = self.api.post(
            '/api/web-features/',
            headers=self.headers,
            json={
                'name': 'Inválida',
                'extra_price': '20.00',
                'web_type_ids': [999999],
            },
        )
        self.assertEqual(unknown.status_code, 400, unknown.text)

        duplicate = self.api.post(
            '/api/web-features/',
            headers=self.headers,
            json={
                'name': 'Duplicada',
                'extra_price': '20.00',
                'web_type_ids': [self.type_a.id, self.type_a.id],
            },
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.text)

    def test_client_rejects_feature_that_does_not_apply_to_web_type(self):
        only_a = self.create_feature('Sólo A', [self.type_a.id])
        global_feature = self.create_feature('Global', [])

        rejected = self.api.post(
            '/api/clients/',
            headers=self.headers,
            json={
                'name': 'Cliente C inválido',
                'document_type': 'RUC',
                'document_number': '20111111111',
                'web_type_id': self.type_c.id,
                'plan': 'alquiler',
                'feature_ids': [only_a['id']],
            },
        )
        self.assertEqual(rejected.status_code, 400, rejected.text)

        accepted = self.api.post(
            '/api/clients/',
            headers=self.headers,
            json={
                'name': 'Cliente C global',
                'document_type': 'RUC',
                'document_number': '20222222222',
                'web_type_id': self.type_c.id,
                'plan': 'alquiler',
                'feature_ids': [global_feature['id']],
            },
        )
        self.assertEqual(accepted.status_code, 201, accepted.text)

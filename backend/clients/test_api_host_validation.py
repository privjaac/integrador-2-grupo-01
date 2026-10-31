from django.test import SimpleTestCase
from django.conf import settings
from fastapi.testclient import TestClient

from api.main import app


class ApiHostValidationTests(SimpleTestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_published_host_is_allowed(self):
        response = self.client.get(
            '/', headers={'Host': 'elisa-backend-apf2.onrender.com'}
        )

        self.assertEqual(response.status_code, 200)

    def test_local_hosts_with_development_port_are_allowed(self):
        for host in ('localhost:8001', '127.0.0.1:8001'):
            with self.subTest(host=host):
                response = self.client.get('/', headers={'Host': host})
                self.assertEqual(response.status_code, 200)

    def test_unlisted_host_is_rejected(self):
        response = self.client.get('/', headers={'Host': 'attacker.invalid'})

        self.assertEqual(response.status_code, 400)

    def test_allowed_hosts_are_explicit_and_have_no_wildcards(self):
        self.assertIn('elisa-backend-apf2.onrender.com', settings.ALLOWED_HOSTS)
        self.assertIn('localhost', settings.ALLOWED_HOSTS)
        self.assertIn('127.0.0.1', settings.ALLOWED_HOSTS)
        self.assertFalse(any('*' in host for host in settings.ALLOWED_HOSTS))

    def test_api_route_remains_reachable_with_allowed_host(self):
        response = self.client.get(
            '/api/users/me',
            headers={'Host': 'elisa-backend-apf2.onrender.com'},
        )

        self.assertEqual(response.status_code, 401)

    def test_cors_preflight_remains_available_for_frontend_origin(self):
        response = self.client.options(
            '/api/auth/login',
            headers={
                'Host': 'elisa-backend-apf2.onrender.com',
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('access-control-allow-origin'),
            'http://localhost:5173',
        )

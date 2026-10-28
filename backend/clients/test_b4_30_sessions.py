import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password, verify_password
from clients.models import Collaborator, CollaboratorSession, PasswordResetRequest, Role

class B430PasswordSessionRevocationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        role_l1 = Role.objects.create(name='B430 Admin', level='L1')
        role_l2 = Role.objects.create(name='B430 Member', level='L2')
        self.admin = Collaborator.objects.create(
            first_name='Admin', last_name='B430', document_number='B430-ADMIN', email='admin-b430@example.test',
            username='admin-b430', password_hash=hash_password('admin-password'), role=role_l1,
        )
        self.account = Collaborator.objects.create(
            first_name='Cuenta', last_name='B430', document_number='B430-ACCOUNT', email='account-b430@example.test',
            username='account-b430', password_hash=hash_password('old-password'), role=role_l2,
        )
        self.other = Collaborator.objects.create(
            first_name='Otra', last_name='B430', document_number='B430-OTHER-USER', email='other-b430@example.test',
            username='other-b430', password_hash=hash_password('other-password'), role=role_l2,
        )
        self.api = TestClient(app)

    def login(self, username, password):
        response = self.api.post('/api/auth/login', json={'username': username, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_password_update_revokes_all_target_sessions_but_not_other_accounts(self):
        admin = self.login(self.admin.username, 'admin-password')
        account_sessions = [self.login(self.account.username, 'old-password') for _ in range(2)]
        other = self.login(self.other.username, 'other-password')
        response = self.api.put(
            f'/api/users/{self.account.id}',
            headers={'Authorization': f"Bearer {admin['access_token']}"},
            json={'password': 'new-password'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        sessions = CollaboratorSession.objects.filter(collaborator=self.account)
        self.assertEqual(sessions.count(), 2)
        self.assertTrue(all(session.revoked_at for session in sessions))
        for token_pair in account_sessions:
            access = self.api.get('/api/users/me', headers={'Authorization': f"Bearer {token_pair['access_token']}"})
            refresh = self.api.post('/api/auth/refresh', json={'refresh_token': token_pair['refresh_token']})
            self.assertEqual(access.status_code, 401)
            self.assertEqual(refresh.status_code, 401)
        self.assertEqual(
            self.api.get('/api/users/me', headers={'Authorization': f"Bearer {other['access_token']}"}).status_code,
            200,
        )
        self.assertEqual(self.login(self.account.username, 'new-password')['token_type'], 'bearer')

    @patch('api.routers.auth.deliver_recovery_email', return_value=True)
    def test_password_reset_revokes_sessions_only_after_single_use_token_succeeds(self, deliver_reset):
        target_tokens = [self.login(self.account.username, 'old-password') for _ in range(2)]
        other_tokens = self.login(self.other.username, 'other-password')
        raw_token = 'b430-single-use-reset-token'
        reset = PasswordResetRequest.objects.create(
            collaborator=self.account, token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        bad = self.api.put('/api/auth/reset-password', json={
            'token': 'wrong-token-that-is-long-enough-to-pass-validation-12345',
            'new_password': 'new-password', 'confirm_password': 'new-password',
        })
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(CollaboratorSession.objects.filter(collaborator=self.account, revoked_at__isnull=True).count(), 2)

        response = self.api.put('/api/auth/reset-password', json={
            'token': raw_token, 'new_password': 'new-password', 'confirm_password': 'new-password',
        })
        self.assertEqual(response.status_code, 200, response.text)
        reset.refresh_from_db()
        self.assertIsNotNone(reset.used_at)
        self.assertEqual(CollaboratorSession.objects.filter(collaborator=self.account, revoked_at__isnull=True).count(), 0)
        for token_pair in target_tokens:
            self.assertEqual(self.api.get('/api/users/me', headers={'Authorization': f"Bearer {token_pair['access_token']}"}).status_code, 401)
            self.assertEqual(self.api.post('/api/auth/refresh', json={'refresh_token': token_pair['refresh_token']}).status_code, 401)
        self.assertEqual(
            self.api.get('/api/users/me', headers={'Authorization': f"Bearer {other_tokens['access_token']}"}).status_code,
            200,
        )
        reused = self.api.put('/api/auth/reset-password', json={
            'token': raw_token, 'new_password': 'third-password', 'confirm_password': 'third-password',
        })
        self.assertEqual(reused.status_code, 400)
        deliver_reset.assert_called_once()

    def test_reset_failure_rolls_back_password_token_consumption_and_session_revocation(self):
        target_tokens = [self.login(self.account.username, 'old-password') for _ in range(2)]
        raw_token = 'b430-rollback-reset-token'
        reset = PasswordResetRequest.objects.create(
            collaborator=self.account, token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        non_raising_api = TestClient(app, raise_server_exceptions=False)
        with patch.object(PasswordResetRequest, 'save', side_effect=RuntimeError('synthetic persistence failure')):
            response = non_raising_api.put('/api/auth/reset-password', json={
                'token': raw_token, 'new_password': 'new-password', 'confirm_password': 'new-password',
            })
        self.assertEqual(response.status_code, 500)
        reset.refresh_from_db()
        self.assertIsNone(reset.used_at)
        self.assertTrue(verify_password('old-password', Collaborator.objects.get(pk=self.account.pk).password_hash))
        self.assertEqual(CollaboratorSession.objects.filter(collaborator=self.account, revoked_at__isnull=True).count(), 2)
        for token_pair in target_tokens:
            self.assertEqual(
                self.api.get('/api/users/me', headers={'Authorization': f"Bearer {token_pair['access_token']}"}).status_code,
                200,
            )

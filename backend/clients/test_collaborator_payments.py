from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TransactionTestCase
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import Collaborator, CollaboratorPayment, Role


class CollaboratorPaymentApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.roles = {
            level: Role.objects.create(name=f'Pago personal {level}', level=level)
            for level in ('L1', 'L2', 'L3', 'L4', 'L5')
        }
        self.people = {}
        self.tokens = {}
        self.api = TestClient(app)
        for level, number in zip(('L1', 'L2', 'L3', 'L4', 'L5'), range(1, 6)):
            person = Collaborator.objects.create(
                first_name='Colaborador', last_name=level,
                document_number=f'PAYEE-{number}', email=f'payee-{level}@example.test',
                username=f'payee-{level}', password_hash=hash_password('test-password'),
                cupe=f'ELO-{number:08d}', role=self.roles[level],
            )
            self.people[level] = person
            login = self.api.post('/api/auth/login', json={
                'username': person.username, 'password': 'test-password',
            })
            self.assertEqual(login.status_code, 200, login.text)
            self.tokens[level] = {'Authorization': f"Bearer {login.json()['access_token']}"}

    def payload(self, **overrides):
        return {
            'collaborator_id': self.people['L5'].id,
            'payment_date': '2026-10-27',
            'amount': '125.50',
            'concept': 'Servicios de soporte',
            'observation': 'Pago del período acordado',
            **overrides,
        }

    def post_payment(self, payload, level='L1', key=None):
        headers = {**self.tokens[level], 'Idempotency-Key': str(key or uuid4())}
        return self.api.post('/api/collaborators/payments/', headers=headers, json=payload)

    def test_sa_sm_register_and_consult_immutable_payment_history(self):
        created = self.post_payment(self.payload(), level='L2')
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        payment = CollaboratorPayment.objects.get(pk=body['id'])
        self.assertEqual(payment.collaborator, self.people['L5'])
        self.assertEqual(payment.registered_by, self.people['L2'])
        self.assertEqual(payment.payment_date, date(2026, 10, 27))
        self.assertEqual(payment.amount, Decimal('125.50'))
        self.assertEqual(body['amount'], '125.50')
        self.assertEqual(payment.concept, 'Servicios de soporte')
        self.assertEqual(payment.reference, f'ELP-{payment.id:08d}')
        self.assertEqual(body['currency'], 'PEN')

        response = self.api.get('/api/collaborators/payments/', headers=self.tokens['L1'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['summary'], {
            'total_paid': '125.50', 'last_payment_date': '2026-10-27', 'count': 1, 'currency': 'PEN',
        })
        self.assertEqual(response.json()['items'][0]['registered_by_id'], self.people['L2'].id)
        self.assertEqual(
            self.api.get('/api/collaborators/payments/collaborators', headers=self.tokens['L2']).json()[0]['id'],
            self.people['L1'].id,
        )

        denied_update = self.api.put(
            f"/api/collaborators/payments/{payment.id}", headers=self.tokens['L1'], json={'amount': '1.00'},
        )
        self.assertIn(denied_update.status_code, (404, 405))
        denied_delete = self.api.delete(
            f"/api/collaborators/payments/{payment.id}", headers=self.tokens['L1'],
        )
        self.assertIn(denied_delete.status_code, (404, 405))
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('125.50'))
        self.assertEqual(CollaboratorPayment.objects.count(), 1)

    def test_only_sa_sm_with_effective_payment_permission_can_read_or_write(self):
        for level in ('L3', 'L4', 'L5'):
            self.assertEqual(self.api.get(
                '/api/collaborators/payments/', headers=self.tokens[level],
            ).status_code, 403)
            self.assertEqual(self.post_payment(self.payload(), level=level).status_code, 403)
        self.assertEqual(CollaboratorPayment.objects.count(), 0)

        restricted_role = Role.objects.create(
            name='L2 sin pagos personales', level='L2', permissions=['users.view'],
        )
        restricted = Collaborator.objects.create(
            first_name='SM', last_name='Limitado', document_number='PAYEE-L2-LIMITED',
            email='payee-l2-limited@example.test', username='payee-l2-limited',
            password_hash=hash_password('test-password'), role=restricted_role,
        )
        login = self.api.post('/api/auth/login', json={
            'username': restricted.username, 'password': 'test-password',
        })
        header = {'Authorization': f"Bearer {login.json()['access_token']}"}
        self.assertEqual(self.api.get('/api/collaborators/payments/', headers=header).status_code, 403)
        denied = self.api.post('/api/collaborators/payments/', headers={
            **header, 'Idempotency-Key': str(uuid4()),
        }, json=self.payload())
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(CollaboratorPayment.objects.count(), 0)

    def test_sa_can_register_a_payment_with_server_generated_reference(self):
        response = self.post_payment(self.payload(), level='L1')
        self.assertEqual(response.status_code, 201, response.text)
        payment = CollaboratorPayment.objects.get(pk=response.json()['id'])
        self.assertEqual(payment.registered_by, self.people['L1'])
        self.assertEqual(payment.reference, f'ELP-{payment.id:08d}')

    def test_validation_rejects_missing_invalid_and_inactive_recipients_without_partial_rows(self):
        headers = self.tokens['L1']
        missing_key = self.api.post('/api/collaborators/payments/', headers=headers, json=self.payload())
        self.assertEqual(missing_key.status_code, 422)
        invalid_payloads = [
            self.payload().copy(),
            self.payload(amount='0'),
            self.payload(amount='-0.01'),
            self.payload(amount='1.001'),
            self.payload(concept='   '),
            self.payload(concept='x' * 151),
            self.payload(observation='x' * 301),
            self.payload(payment_date='not-a-date'),
            self.payload(reference='FORGED-REFERENCE'),
        ]
        invalid_payloads[0].pop('concept')
        for payload in invalid_payloads:
            response = self.api.post('/api/collaborators/payments/', headers={
                **headers, 'Idempotency-Key': str(uuid4()),
            }, json=payload)
            self.assertEqual(response.status_code, 422, response.text)

        missing = self.api.post('/api/collaborators/payments/', headers={**headers, 'Idempotency-Key': str(uuid4())},
                                json=self.payload(collaborator_id=999999))
        self.assertEqual(missing.status_code, 404)
        self.people['L5'].is_active = False
        self.people['L5'].save(update_fields=['is_active'])
        inactive = self.post_payment(self.payload())
        self.assertEqual(inactive.status_code, 404)
        self.assertEqual(CollaboratorPayment.objects.count(), 0)

    def test_filters_and_generated_references_are_distinct(self):
        for idx, (level, concept, amount, when) in enumerate([
            ('L4', 'Soporte técnico', '100.00', '2026-10-20'),
            ('L5', 'Capacitación', '75.00', '2026-10-21'),
            ('L4', 'Soporte nocturno', '25.00', '2026-10-21'),
        ]):
            response = self.post_payment(self.payload(
                collaborator_id=self.people[level].id, concept=concept, amount=amount, payment_date=when,
            ))
            self.assertEqual(response.status_code, 201, response.text)
        history = self.api.get('/api/collaborators/payments/?concept=soporte', headers=self.tokens['L2']).json()
        self.assertEqual(history['summary']['count'], 2)
        self.assertEqual(history['summary']['total_paid'], '125.00')
        self.assertEqual(history['items'][0]['concept'], 'Soporte nocturno')
        self.assertEqual(len({item['reference'] for item in history['items']}), 2)
        filtered = self.api.get(
            f"/api/collaborators/payments/?collaborator_id={self.people['L4'].id}&payment_date=2026-10-21",
            headers=self.tokens['L1'],
        ).json()
        self.assertEqual(filtered['summary']['count'], 1)
        self.assertEqual(filtered['items'][0]['concept'], 'Soporte nocturno')

    def test_idempotent_replay_does_not_duplicate_payment_or_allow_key_reuse(self):
        key = uuid4()
        first = self.post_payment(self.payload(), key=key)
        self.assertEqual(first.status_code, 201, first.text)
        replay = self.post_payment(self.payload(), key=key)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()['id'], first.json()['id'])
        altered = self.post_payment(self.payload(amount='126.00'), key=key)
        self.assertEqual(altered.status_code, 409)
        self.assertEqual(CollaboratorPayment.objects.count(), 1)

from datetime import timedelta

from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import (
    Client, ClientChangeRequest, ClientHistory, Collaborator, CommercialPaymentNotice,
    CommercialPaymentNoticeConfig, ContractedService, DocumentedPaymentDue,
    InternalNotification, Role, WebCatalog,
)

class B430CommercialWorkflowTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.roles = {}
        self.people = {}
        self.headers = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'B430 {level}', level=level)
            person = Collaborator.objects.create(
                first_name='B430', last_name=level, document_number=f'B430-DOC-{level}',
                email=f'b430-{level}@example.test', phone=f'+5199000000{level[-1]}',
                username=f'b430-{level.lower()}', password_hash=hash_password('test-password'), role=role,
            )
            self.roles[level] = role
            self.people[level] = person
        self.offer = WebCatalog.objects.create(name='B430 servicio', base_price_rent=10, base_price_sale=100)
        self.client_record = Client.objects.create(
            name='Cliente B430', document_type='DNI', document_number='B430-CLIENT',
            email='cliente-b430@example.test', phone='+51991112222', status='activo',
            web_type=self.offer, next_payment_date=timezone.localdate() + timedelta(days=7),
        )
        self.other_client = Client.objects.create(
            name='Otro cliente B430', document_type='DNI', document_number='B430-OTHER',
            status='activo', web_type=self.offer,
        )
        self.service = ContractedService.objects.create(
            client=self.client_record, service_name='Mantenimiento B430', recorded_by=self.people['L2'],
            commitment_reference='OC-B430-1', scope='Alcance documentado', frequency='mensual',
            evidence_reference='DOC-B430-OC',
        )
        self.other_service = ContractedService.objects.create(
            client=self.other_client, service_name='Servicio ajeno', recorded_by=self.people['L2'],
            commitment_reference='OC-B430-2', scope='Otro alcance', frequency='unica',
            evidence_reference='DOC-B430-OTRO',
        )
        self.api = TestClient(app)
        for level, person in self.people.items():
            response = self.api.post('/api/auth/login', json={
                'username': person.username, 'password': 'test-password',
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.headers[level] = {'Authorization': f"Bearer {response.json()['access_token']}"}

        # TransactionTestCase flushes data-migration rows between tests.
        for channel, days in {
            'whatsapp': [7, 3, 1], 'email': [7], 'internal': [7, 3, 1],
        }.items():
            CommercialPaymentNoticeConfig.objects.get_or_create(
                channel=channel, defaults={'anticipation_days': days, 'is_active': True},
            )

    def test_responsible_assignment_uses_crm_approval_and_preserves_history(self):
        self.people['L5'].is_active = False
        self.people['L5'].save(update_fields=['is_active'])
        ineligible = self.api.post(
            f'/api/clients/{self.client_record.id}/change-requests', headers=self.headers['L2'],
            json={'changes': {'commercial_responsible_id': self.people['L5'].id}, 'reason': 'No elegible'},
        )
        self.assertEqual(ineligible.status_code, 409)
        self.assertEqual(ClientChangeRequest.objects.count(), 0)
        response = self.api.post(
            f'/api/clients/{self.client_record.id}/change-requests', headers=self.headers['L2'],
            json={'changes': {'commercial_responsible_id': self.people['L4'].id}, 'reason': 'Asignación documentada'},
        )
        self.assertEqual(response.status_code, 201, response.text)
        request = ClientChangeRequest.objects.get(pk=response.json()['id'])
        self.client_record.refresh_from_db()
        self.assertIsNone(self.client_record.commercial_responsible_id)

        denied = self.api.post(
            f'/api/clients/{self.client_record.id}/change-requests', headers=self.headers['L3'],
            json={'changes': {'commercial_responsible_id': self.people['L4'].id}, 'reason': 'Fuera de competencia'},
        )
        self.assertEqual(denied.status_code, 403)
        direct = self.api.put(
            f'/api/clients/{self.client_record.id}', headers=self.headers['L2'],
            json={'commercial_responsible_id': self.people['L4'].id},
        )
        self.assertGreaterEqual(direct.status_code, 400)

        resolved = self.api.post(
            f'/api/clients/requests/{request.id}/resolve', headers=self.headers['L1'],
            json={'decision': 'aprobado', 'reason': 'Aprobación CRM'},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.commercial_responsible_id, self.people['L4'].id)
        history = list(ClientHistory.objects.filter(client=self.client_record).order_by('id'))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1].actor_id, self.people['L1'].id)
        self.assertEqual(history[-1].after_data['commercial_responsible_id'], self.people['L4'].id)
        self.assertEqual(history[-1].request_id, request.id)

        l2_client = self.api.get(f'/api/clients/{self.client_record.id}', headers=self.headers['L2'])
        self.assertEqual(l2_client.json()['commercial_responsible_id'], self.people['L4'].id)
        self.assertTrue(l2_client.json()['commercial_responsible_active'])
        l3_client = self.api.get(f'/api/clients/{self.client_record.id}', headers=self.headers['L3'])
        self.assertNotEqual(l3_client.json().get('commercial_responsible_name'), 'B430 L4')
        eligible = self.api.get('/api/clients/commercial-responsibles/eligible', headers=self.headers['L2'])
        self.assertEqual(eligible.status_code, 200, eligible.text)
        self.assertNotIn(self.people['L5'].id, {person['id'] for person in eligible.json()})

        removal = self.api.post(
            f'/api/clients/{self.client_record.id}/change-requests', headers=self.headers['L2'],
            json={'changes': {'commercial_responsible_id': None}, 'reason': 'Retiro aprobado'},
        )
        self.assertEqual(removal.status_code, 201, removal.text)
        removed = self.api.post(
            f"/api/clients/requests/{removal.json()['id']}/resolve", headers=self.headers['L1'],
            json={'decision': 'aprobado', 'reason': 'Se retira asignación'},
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.client_record.refresh_from_db()
        self.assertIsNone(self.client_record.commercial_responsible_id)
        self.assertEqual(ClientHistory.objects.filter(client=self.client_record).count(), 4)

    def test_l2_documents_due_only_for_its_client_and_notice_generation_is_idempotent(self):
        # A legacy client-level date alone is not a documented obligation.
        call_command('prepare_commercial_payment_notices', verbosity=0)
        self.assertEqual(DocumentedPaymentDue.objects.count(), 0)
        self.assertEqual(CommercialPaymentNotice.objects.count(), 0)
        payload = {
            'service_id': self.service.id,
            'due_date': (timezone.localdate() + timedelta(days=7)).isoformat(),
            'obligation_reference': 'OBL-B430-1', 'evidence_reference': 'DOC-B430-VENC-1',
        }
        forbidden = self.api.post(
            f'/api/clients/{self.client_record.id}/documented-payment-dues',
            headers=self.headers['L1'], json=payload,
        )
        self.assertEqual(forbidden.status_code, 403)
        wrong_service = self.api.post(
            f'/api/clients/{self.client_record.id}/documented-payment-dues',
            headers=self.headers['L2'], json={**payload, 'service_id': self.other_service.id},
        )
        self.assertEqual(wrong_service.status_code, 409)
        missing_evidence = self.api.post(
            f'/api/clients/{self.client_record.id}/documented-payment-dues',
            headers=self.headers['L2'], json={
                'service_id': self.service.id, 'due_date': payload['due_date'],
                'obligation_reference': ' ', 'evidence_reference': '',
            },
        )
        self.assertEqual(missing_evidence.status_code, 422)
        self.assertEqual(DocumentedPaymentDue.objects.count(), 0)

        payload.pop('obligation_reference')

        response = self.api.post(
            f'/api/clients/{self.client_record.id}/documented-payment-dues',
            headers=self.headers['L2'], json=payload,
        )
        self.assertEqual(response.status_code, 201, response.text)
        due = DocumentedPaymentDue.objects.get()
        self.assertEqual(due.recorded_by_id, self.people['L2'].id)
        self.assertEqual(due.service.client_id, self.client_record.id)
        self.assertEqual(due.obligation_reference, '')
        self.assertEqual(due.evidence_reference, 'DOC-B430-VENC-1')

        call_command('prepare_commercial_payment_notices', verbosity=0)
        call_command('prepare_commercial_payment_notices', verbosity=0)
        notices = list(CommercialPaymentNotice.objects.filter(due=due).order_by('channel'))
        self.assertEqual(len(notices), 3)
        self.assertEqual({n.channel: n.status for n in notices}, {
            'email': 'preparada', 'internal': 'fallida', 'whatsapp': 'preparada',
        })
        self.assertTrue(all(n.status != 'entregada' for n in notices))
        self.assertEqual(InternalNotification.objects.filter(commercial_due=due).count(), 0)
        self.assertEqual(CommercialPaymentNotice.objects.filter(due=due).count(), 3)
        self.assertEqual(DocumentedPaymentDue.objects.filter(due_date=self.client_record.next_payment_date).count(), 1)

    def test_internal_notice_only_reaches_current_active_responsible_and_has_no_financial_detail(self):
        self.client_record.commercial_responsible = self.people['L4']
        self.client_record.save(update_fields=['commercial_responsible'])
        due = DocumentedPaymentDue.objects.create(
            client=self.client_record, service=self.service,
            due_date=timezone.localdate() + timedelta(days=3),
            obligation_reference='OBL-PRIVADA', evidence_reference='DOC-PRIVADO', recorded_by=self.people['L2'],
        )
        call_command('prepare_commercial_payment_notices', verbosity=0)
        notice = CommercialPaymentNotice.objects.get(due=due, channel='internal')
        self.assertEqual(notice.status, 'disponible')
        self.assertEqual(notice.recipient_id, self.people['L4'].id)
        self.assertNotIn('OBL-PRIVADA', notice.message)
        self.assertNotIn('DOC-PRIVADO', notice.message)
        self.assertNotIn(self.client_record.name, notice.message)

        inbox = self.api.get('/api/notifications/internal/', headers=self.headers['L4'])
        self.assertEqual(inbox.status_code, 200, inbox.text)
        self.assertEqual(inbox.json()['unread_count'], 1)
        item = inbox.json()['items'][0]
        self.assertIsNone(item['task_id'])
        self.assertNotIn('client_id', item)
        other = self.api.get('/api/notifications/internal/', headers=self.headers['L3'])
        self.assertEqual(other.json()['unread_count'], 0)
        marked = self.api.patch(f"/api/notifications/internal/{item['id']}/read", headers=self.headers['L4'])
        self.assertEqual(marked.status_code, 200, marked.text)

        self.client_record.commercial_responsible = None
        self.client_record.save(update_fields=['commercial_responsible'])
        no_longer_owner = self.api.get('/api/notifications/internal/', headers=self.headers['L4'])
        self.assertEqual(no_longer_owner.json()['items'], [])
        hidden = self.api.patch(f"/api/notifications/internal/{item['id']}/read", headers=self.headers['L4'])
        self.assertEqual(hidden.status_code, 404)

    def test_without_owner_and_with_missing_contact_notices_are_recorded_as_failed(self):
        self.client_record.commercial_responsible = self.people['L4']
        self.client_record.email = ''
        self.client_record.phone = ''
        self.client_record.save(update_fields=['email', 'phone'])
        self.people['L4'].is_active = False
        self.people['L4'].save(update_fields=['is_active'])
        l2_client = self.api.get(f'/api/clients/{self.client_record.id}', headers=self.headers['L2'])
        self.assertFalse(l2_client.json()['commercial_responsible_active'])
        due = DocumentedPaymentDue.objects.create(
            client=self.client_record, service=self.service,
            due_date=timezone.localdate() + timedelta(days=1),
            obligation_reference='OBL-SIN-DATOS', evidence_reference='DOC-SIN-DATOS', recorded_by=self.people['L2'],
        )
        call_command('prepare_commercial_payment_notices', verbosity=0)
        rows = {notice.channel: notice for notice in CommercialPaymentNotice.objects.filter(due=due)}
        self.assertEqual(set(rows), {'internal', 'whatsapp'})
        self.assertTrue(all(item.status == 'fallida' for item in rows.values()))
        self.assertEqual(InternalNotification.objects.filter(commercial_due=due).count(), 0)

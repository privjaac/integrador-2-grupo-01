from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from fastapi.testclient import TestClient

from api.main import app
from api.routers.auth import hash_password
from clients.models import (
    Client, Collaborator, CommercialPaymentNotice, CommercialPaymentNoticeConfig,
    CommercialPaymentNoticeConfigEvent, ContractedService, DocumentedPaymentDue,
    InternalNotification, Role,
)


class CommercialNotificationCenterTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.people = {}
        self.headers = {}
        for level in ('L1', 'L2', 'L3', 'L4'):
            role = Role.objects.create(name=f'PB-NOT {level}', level=level)
            person = Collaborator.objects.create(
                first_name='Notice', last_name=level, document_number=f'PB-NOT-{level}',
                email=f'pb-not-{level}@example.test', phone=f'+5199000000{level[-1]}',
                username=f'pb-not-{level.lower()}', password_hash=hash_password('test-password'), role=role,
            )
            self.people[level] = person
        self.api = TestClient(app)
        for level, person in self.people.items():
            response = self.api.post('/api/auth/login', json={
                'username': person.username, 'password': 'test-password',
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.headers[level] = {'Authorization': f"Bearer {response.json()['access_token']}"}

        from clients.models import WebCatalog
        offer = WebCatalog.objects.create(name='PB-NOT service', base_price_rent=10, base_price_sale=100)
        self.client_record = Client.objects.create(
            name='Cliente PB-NOT', document_type='DNI', document_number='PB-NOT-CLIENT',
            email='contacto-private@example.test', phone='+51998887766', status='activo', web_type=offer,
            commercial_responsible=self.people['L4'],
        )
        self.service = ContractedService.objects.create(
            client=self.client_record, service_name='Servicio documentado', recorded_by=self.people['L2'],
            commitment_reference='COMP-PB-NOT', scope='Alcance registrado', frequency='mensual',
            evidence_reference='EVIDENCIA-PB-NOT',
        )
        self.due = DocumentedPaymentDue.objects.create(
            client=self.client_record, service=self.service,
            due_date=timezone.localdate() + timedelta(days=3),
            obligation_reference='OBLIGACION-PRIVADA', evidence_reference='EVIDENCIA-PRIVADA',
            recorded_by=self.people['L2'],
        )

    def test_config_is_scoped_audited_and_controls_preparation_without_claiming_delivery(self):
        response = self.api.put(
            '/api/notifications/commercial-notice-config/whatsapp', headers=self.headers['L2'],
            json={'anticipation_days': [5, 2], 'is_active': True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['anticipation_days'], [5, 2])
        self.assertEqual(CommercialPaymentNoticeConfigEvent.objects.count(), 1)
        history = CommercialPaymentNoticeConfigEvent.objects.get()
        self.assertEqual(history.actor_id, self.people['L2'].id)
        history.new_active = False
        with self.assertRaises(ValueError):
            history.save()
        with self.assertRaises(ValueError):
            history.delete()

        denied = self.api.put(
            '/api/notifications/commercial-notice-config/whatsapp', headers=self.headers['L3'],
            json={'anticipation_days': [3], 'is_active': True},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(CommercialPaymentNoticeConfigEvent.objects.count(), 1)
        invalid = self.api.put(
            '/api/notifications/commercial-notice-config/email', headers=self.headers['L2'],
            json={'anticipation_days': [0, 0], 'is_active': True},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(CommercialPaymentNoticeConfigEvent.objects.count(), 1)
        l4_panel = self.api.get('/api/notifications/upcoming', headers=self.headers['L4'])
        self.assertEqual(l4_panel.status_code, 403)

        from django.core.management import call_command
        call_command('prepare_commercial_payment_notices', verbosity=0)
        notices = list(CommercialPaymentNotice.objects.filter(due=self.due).order_by('channel'))
        self.assertEqual({notice.channel for notice in notices}, {'internal'})
        self.assertEqual({notice.status for notice in notices}, {'disponible'})
        self.assertTrue(all(notice.status != 'entregada' for notice in notices))
        self.assertEqual(InternalNotification.objects.filter(commercial_due=self.due).count(), 1)

    def test_l3_panel_and_history_hide_contact_and_commercial_evidence(self):
        notice = CommercialPaymentNotice.objects.create(
            due=self.due, channel='email', anticipation_days=3, recipient=None,
            destination_snapshot=self.client_record.email, source_key='pb-not-external-source',
            status='preparada', title='Aviso preparado', message='Compromiso próximo.',
        )
        upcoming = self.api.get('/api/notifications/upcoming', headers=self.headers['L3'])
        self.assertEqual(upcoming.status_code, 200, upcoming.text)
        row = next(item for item in upcoming.json()['items'] if item['id'] == notice.id)
        self.assertEqual(row['status'], 'preparada')
        self.assertEqual(row['recipient'], 'Cliente')
        self.assertNotIn(self.client_record.email, upcoming.text)

        detail = self.api.get(f'/api/notifications/logs/{notice.id}', headers=self.headers['L3'])
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertIsNone(detail.json()['evidence_reference'])
        self.assertIsNone(detail.json()['obligation_reference'])
        self.assertNotIn(self.client_record.email, detail.text)
        self.assertNotIn('EVIDENCIA-PRIVADA', detail.text)

        history = self.api.get('/api/notifications/logs?channel=email', headers=self.headers['L3'])
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()['count'], 1)

    def test_internal_failed_notice_can_be_retried_once_but_external_preparation_cannot(self):
        internal = CommercialPaymentNotice.objects.create(
            due=self.due, channel='internal', anticipation_days=3, recipient=None,
            source_key='pb-not-internal-failed', status='fallida', title='Aviso interno',
            message='Seguimiento.', error_message='No existía responsable.',
        )
        external = CommercialPaymentNotice.objects.create(
            due=self.due, channel='whatsapp', anticipation_days=3, recipient=None,
            destination_snapshot=self.client_record.phone, source_key='pb-not-external-prepared',
            status='preparada', title='Aviso externo preparado', message='Compromiso próximo.',
        )
        rejected_external = self.api.post(
            f'/api/notifications/logs/{external.id}/resend', headers=self.headers['L2'],
        )
        self.assertEqual(rejected_external.status_code, 409)
        self.assertEqual(CommercialPaymentNotice.objects.filter(resend_of=external).count(), 0)

        success = self.api.post(
            f'/api/notifications/logs/{internal.id}/resend', headers=self.headers['L2'],
        )
        self.assertEqual(success.status_code, 201, success.text)
        attempt = CommercialPaymentNotice.objects.get(resend_of=internal)
        self.assertEqual(attempt.status, 'disponible')
        self.assertEqual(attempt.resent_by_id, self.people['L2'].id)
        self.assertEqual(attempt.recipient_id, self.people['L4'].id)
        self.assertEqual(InternalNotification.objects.filter(source_key=attempt.source_key).count(), 1)
        duplicate = self.api.post(
            f'/api/notifications/logs/{internal.id}/resend', headers=self.headers['L2'],
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(CommercialPaymentNotice.objects.filter(resend_of=internal).count(), 1)

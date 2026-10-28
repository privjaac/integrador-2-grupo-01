from datetime import date
from decimal import Decimal

from django.test import TestCase
from fastapi import HTTPException

from api.routers.clients import (
    confirm_client_payment, confirm_payment_adjustment, list_client_payments,
    record_client_payment, record_payment_adjustment,
)
from api.schemas.clients import CustomerPaymentWrite, PaymentAdjustmentWrite
from clients.models import Client, Collaborator, ContractedService, CustomerPayment, Role, WebCatalog


class CustomerPaymentTests(TestCase):
    def setUp(self):
        self.l2_role = Role.objects.create(name='Cobros L2', level='L2')
        self.l1_role = Role.objects.create(name='Cobros L1', level='L1')
        self.l2 = Collaborator.objects.create(first_name='L2', last_name='Cobros', document_number='PAY-L2',
            email='pay-l2@example.test', username='pay-l2', role=self.l2_role)
        self.l1 = Collaborator.objects.create(first_name='L1', last_name='Cobros', document_number='PAY-L1',
            email='pay-l1@example.test', username='pay-l1', role=self.l1_role)
        catalog = WebCatalog.objects.create(name='Pago test', base_price_rent=10, base_price_sale=100)
        self.client_obj = Client.objects.create(name='Cliente cobro', document_type='DNI', document_number='PAY-CLIENT', web_type=catalog)
        self.service = ContractedService.objects.create(client=self.client_obj, service_name='Soporte',
            catalog_service=catalog, commitment_reference='CONT-PAY-1', scope='Soporte mensual',
            agreed_amount=Decimal('100.00'), currency='PEN', frequency='mensual', effective_start=date(2026, 1, 1),
            evidence_reference='DOC-CONT-1', recorded_by=self.l2)
        self.actor = {'role': 'L2', 'collaborator_id': self.l2.id}

    def payload(self, **overrides):
        values = {'service_id': self.service.id, 'reference': 'REC-001', 'amount': '40.00', 'currency': 'PEN',
            'effective_date': '2026-10-01', 'evidence_reference': 'RECIBO-001'}
        values.update(overrides)
        return CustomerPaymentWrite(**values)

    def test_registration_is_pending_and_only_explicit_confirmation_counts(self):
        row = record_client_payment(self.client_obj.id, self.payload(), self.actor)
        self.assertIsNone(row['confirmed_at'])
        self.assertEqual(row['confirmed_net'], Decimal('0'))
        pending = CustomerPayment.objects.get(pk=row['id'])
        confirm_client_payment(pending.id, {'evidence_reference': 'REVISION-001'}, self.actor)
        self.assertEqual(list_client_payments(self.client_obj.id, self.actor)[0]['confirmed_net'], Decimal('40.00'))
        with self.assertRaises(HTTPException) as caught:
            confirm_client_payment(pending.id, {'evidence_reference': 'REVISION-002'}, self.actor)
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_reference_and_non_l2_write_are_denied(self):
        record_client_payment(self.client_obj.id, self.payload(), self.actor)
        with self.assertRaises(HTTPException) as duplicate:
            record_client_payment(self.client_obj.id, self.payload(), self.actor)
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as forbidden:
            record_client_payment(self.client_obj.id, self.payload(reference='REC-002'),
                {'role': 'L1', 'collaborator_id': self.l1.id})
        self.assertEqual(forbidden.exception.status_code, 403)
        self.assertEqual(CustomerPayment.objects.count(), 1)

    def test_adjustment_is_separate_linked_and_preserves_original(self):
        row = record_client_payment(self.client_obj.id, self.payload(), self.actor)
        payment = CustomerPayment.objects.get(pk=row['id'])
        confirm_client_payment(payment.id, {'evidence_reference': 'REVISION-001'}, self.actor)
        adjustment = record_payment_adjustment(payment.id, PaymentAdjustmentWrite(amount='-10.00', reason='Corrección',
            evidence_reference='AJUSTE-001'), self.actor)
        self.assertEqual(payment.amount, Decimal('40.00'))
        self.assertEqual(payment.adjustments.count(), 1)
        self.assertIsNone(payment.adjustments.get(pk=adjustment['id']).confirmed_at)
        confirm_payment_adjustment(adjustment['id'], {}, self.actor)
        self.assertEqual(list_client_payments(self.client_obj.id, self.actor)[0]['confirmed_net'], Decimal('30.00'))

    def test_receipt_must_match_service_client_and_currency(self):
        with self.assertRaises(HTTPException):
            record_client_payment(self.client_obj.id, self.payload(service_id=99999), self.actor)
        with self.assertRaises(HTTPException):
            record_client_payment(self.client_obj.id, self.payload(reference='REC-002', currency='USD'), self.actor)
        self.assertEqual(CustomerPayment.objects.count(), 0)

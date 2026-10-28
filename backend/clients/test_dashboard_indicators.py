from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from fastapi import HTTPException

from api.routers.dashboard import build_dashboard_summary
from clients.models import (
    Client, ClientFeature, Collaborator, ContractedService, CustomerPayment,
    CustomerPaymentAdjustment, Role, WebCatalog, WebFeature,
)


class DashboardIndicatorTests(TestCase):
    def setUp(self):
        self.roles = {level: Role.objects.create(name=f'Dashboard {level}', level=level)
                      for level in ('L1', 'L2', 'L3', 'L4')}
        self.actors = {level: Collaborator.objects.create(
            first_name='Dashboard', last_name=level, document_number=f'DASH-{level}',
            email=f'dash-{level}@example.test', username=f'dash-{level}', role=self.roles[level],
        ) for level in self.roles}
        self.catalog = WebCatalog.objects.create(name='Web operativa', base_price_rent=10, base_price_sale=100)
        self.client_obj = Client.objects.create(
            name='Cliente operativo', document_type='DNI', document_number='DASH-CLIENT',
            web_type=self.catalog, status='activo', plan='alquiler',
            registration_date=date(2026, 1, 1), next_payment_date=date(2026, 2, 1),
            total_price=Decimal('9999.00'),
        )
        self.feature = WebFeature.objects.create(name='Chatbot', extra_price=10)
        ClientFeature.objects.create(client=self.client_obj, feature=self.feature)
        self.service = ContractedService.objects.create(
            client=self.client_obj, service_name='Hosting', catalog_service=self.catalog,
            commitment_reference='DASH-COMMIT', scope='Hosting mensual', agreed_amount=Decimal('100.00'),
            currency='PEN', frequency='mensual', effective_start=date(2026, 9, 28),
            documented_expiration=date(2026, 11, 15),
            evidence_reference='DASH-DOC', recorded_by=self.actors['L2'],
        )

    def _payment(self, reference, amount, currency, effective, confirmed=True):
        return CustomerPayment.objects.create(
            client=self.client_obj, service=self.service, reference=reference,
            amount=Decimal(amount), currency=currency, effective_date=effective,
            evidence_reference=reference, recorded_by=self.actors['L2'],
            confirmed_by=self.actors['L2'] if confirmed else None,
            confirmed_at=timezone.now() if confirmed else None,
            confirmation_evidence=reference if confirmed else '',
        )

    def test_revenue_counts_only_confirmed_receipts_and_adjustments_by_currency(self):
        pen = self._payment('PEN-1', '100.00', 'PEN', date(2026, 10, 5))
        CustomerPaymentAdjustment.objects.create(
            payment=pen, amount=Decimal('-20.00'), reason='Corrección confirmada',
            evidence_reference='ADJ-1', recorded_by=self.actors['L2'],
            confirmed_by=self.actors['L2'], confirmed_at=timezone.now(),
        )
        CustomerPaymentAdjustment.objects.create(
            payment=pen, amount=Decimal('5.00'), reason='Ajuste confirmado positivo',
            evidence_reference='ADJ-3', recorded_by=self.actors['L2'],
            confirmed_by=self.actors['L2'], confirmed_at=timezone.now(),
        )
        CustomerPaymentAdjustment.objects.create(
            payment=pen, amount=Decimal('30.00'), reason='Pendiente',
            evidence_reference='ADJ-2', recorded_by=self.actors['L2'],
        )
        self._payment('PENDING', '500.00', 'PEN', date(2026, 10, 6), confirmed=False)
        self._payment('USD-1', '50.00', 'USD', date(2025, 11, 30))
        self._payment('OLD', '900.00', 'PEN', date(2025, 10, 31))
        summary = build_dashboard_summary(
            {'role': 'L1', 'collaborator_id': self.actors['L1'].id}, date(2026, 10, 27),
        )
        series = {item['currency']: item['months'] for item in summary['monthly_revenue']}
        self.assertEqual(set(series), {'PEN', 'USD'})
        self.assertEqual(len(series['PEN']), 12)
        self.assertEqual(series['PEN'][-1]['amount'], '85.00')
        self.assertEqual(series['PEN'][0]['period'], '2025-11')
        self.assertEqual(series['PEN'][0]['amount'], '0.00')
        self.assertEqual(series['USD'][0]['amount'], '50.00')

    def test_service_activity_expiration_and_recurrence_use_contract_dates(self):
        summary = build_dashboard_summary(
            {'role': 'L3', 'collaborator_id': self.actors['L3'].id}, date(2026, 10, 27),
        )
        self.assertEqual([row['service_id'] for row in summary['services']['active']], [self.service.id])
        active = summary['services']['active'][0]
        self.assertEqual(active['features'], ['Chatbot'])
        self.assertEqual(active['web_type_name'], 'Web operativa')
        self.assertEqual(summary['services']['upcoming_expirations_30_days'][0]['documented_expiration'], date(2026, 11, 15))
        self.assertEqual(summary['services']['upcoming_recurrences_30_days'][0]['next_recurrence_date'], date(2026, 10, 28))
        self.assertNotIn('monthly_revenue', summary)
        self.assertNotIn('total_price', summary['clients'][0])

        expired = ContractedService.objects.create(
            client=self.client_obj, service_name='Expired', commitment_reference='DASH-EXPIRED',
            scope='Terminado', frequency='unica', effective_start=date(2026, 1, 1),
            documented_expiration=date(2026, 10, 1), evidence_reference='DOC-EXP',
            recorded_by=self.actors['L2'],
        )
        summary = build_dashboard_summary(
            {'role': 'L3', 'collaborator_id': self.actors['L3'].id}, date(2026, 10, 27),
        )
        self.assertIn(expired.id, [row['service_id'] for row in summary['services']['expired']])
        self.assertNotIn(expired.id, [row['service_id'] for row in summary['services']['active']])

    def test_annual_recurrence_uses_contract_start_as_anchor(self):
        annual = ContractedService.objects.create(
            client=self.client_obj, service_name='Dominio anual', commitment_reference='DASH-YEARLY',
            scope='Dominio anual', frequency='anual', effective_start=date(2025, 10, 28),
            evidence_reference='DOC-YEARLY', recorded_by=self.actors['L2'],
        )
        summary = build_dashboard_summary(
            {'role': 'L3', 'collaborator_id': self.actors['L3'].id}, date(2026, 10, 27),
        )
        annual_due = next(
            item for item in summary['services']['upcoming_recurrences_30_days']
            if item['service_id'] == annual.id
        )
        self.assertEqual(annual_due['next_recurrence_date'], date(2026, 10, 28))
        self.assertNotIn(annual.id, [row['service_id'] for row in summary['services']['expired']])

    def test_dashboard_permissions_and_financial_scope(self):
        for level in ('L1', 'L2'):
            response = build_dashboard_summary(
                {'role': level, 'collaborator_id': self.actors[level].id}, date(2026, 10, 27),
            )
            self.assertIn('monthly_revenue', response)
        with self.assertRaises(HTTPException) as denied:
            build_dashboard_summary({'role': 'L4', 'collaborator_id': self.actors['L4'].id})
        self.assertEqual(denied.exception.status_code, 403)
        with self.assertRaises(HTTPException) as inactive:
            build_dashboard_summary({'role': 'L3', 'collaborator_id': self.actors['L4'].id})
        self.assertEqual(inactive.exception.status_code, 403)

    def test_known_contract_currency_has_zero_monthly_series_without_confirmed_receipts(self):
        summary = build_dashboard_summary(
            {'role': 'L2', 'collaborator_id': self.actors['L2'].id}, date(2026, 10, 27),
        )
        series = {item['currency']: item['months'] for item in summary['monthly_revenue']}
        self.assertEqual(set(series), {'PEN'})
        self.assertEqual(len(series['PEN']), 12)
        self.assertTrue(all(month['amount'] == '0.00' for month in series['PEN']))

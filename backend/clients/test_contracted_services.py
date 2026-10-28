from datetime import date

from fastapi.testclient import TestClient
from django.test import TransactionTestCase

from api.main import app
from api.routers.auth import hash_password
from api.routers.clients import service_next_due_date
from clients.models import (
    Client, Collaborator, ContractedService, ContractedServiceHistory,
    Project, ProjectContractedService, ProjectCoordination, Role, WebCatalog,
)


class ContractedServiceApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.tokens = {}
        self.actors = {}
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            role = Role.objects.create(name=f'Servicios {level}', level=level)
            actor = Collaborator.objects.create(
                first_name='Servicio', last_name=level,
                document_number=f'SERVICE-API-{level}', email=f'service-api-{level}@example.com',
                username=f'service-api-{level}', password_hash=hash_password('test-password'), role=role,
            )
            self.actors[level] = actor
        self.offer = WebCatalog.objects.create(name='Servicio web', base_price_rent=10, base_price_sale=100)
        self.other_offer = WebCatalog.objects.create(name='Otra oferta', base_price_rent=20, base_price_sale=200)
        self.client_a = Client.objects.create(name='Cliente A', document_type='DNI', document_number='SERVICE-CLIENT-A', web_type=self.offer)
        self.client_b = Client.objects.create(name='Cliente B', document_type='DNI', document_number='SERVICE-CLIENT-B', web_type=self.offer)
        self.project_a = Project.objects.create(client=self.client_a, name='Proyecto A')
        self.project_b = Project.objects.create(client=self.client_b, name='Proyecto B')
        ProjectCoordination.objects.create(project=self.project_a, coordinator=self.actors['L3'], assigned_by=self.actors['L2'])
        ProjectCoordination.objects.create(project=self.project_b, coordinator=self.actors['L3'], assigned_by=self.actors['L2'])
        self.api = TestClient(app)
        for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
            login = self.api.post('/api/auth/login', json={'username': f'service-api-{level}', 'password': 'test-password'})
            self.tokens[level] = {'Authorization': f"Bearer {login.json()['access_token']}"}

    def payload(self, **overrides):
        return {
            'service_name': 'Desarrollo web', 'catalog_service_id': self.offer.id,
            'commitment_reference': 'OC-2026-01',
            'scope': 'Desarrollo web y soporte incluido', 'agreed_amount': '150.00', 'currency': 'PEN',
            'frequency': 'mensual', 'effective_start': '2026-01-31',
            'evidence_reference': 'DOC-OC-2026-01', 'reason': 'Registro de compromiso aprobado',
            **overrides,
        }

    def test_l2_records_commitment_and_history_and_noncommercial_roles_cannot_write(self):
        response = self.api.post(
            f'/api/clients/{self.client_a.id}/contracted-services',
            headers=self.tokens['L2'], json=self.payload(),
        )
        self.assertEqual(response.status_code, 201, response.text)
        service = ContractedService.objects.get()
        self.assertEqual(service.recorded_by, self.actors['L2'])
        self.assertEqual(ContractedServiceHistory.objects.filter(service=service, action='registro').count(), 1)
        self.assertEqual(response.json()['next_due_date'], service_next_due_date(service).isoformat())
        l3_list = self.api.get(
            f'/api/clients/{self.client_a.id}/contracted-services', headers=self.tokens['L3'],
        )
        self.assertEqual(l3_list.status_code, 200)
        self.assertNotIn('agreed_amount', l3_list.json()[0])
        self.assertNotIn('currency', l3_list.json()[0])
        for level in ('L1', 'L3', 'L4', 'L5'):
            denied = self.api.post(
                f'/api/clients/{self.client_a.id}/contracted-services',
                headers=self.tokens[level], json=self.payload(),
            )
            self.assertEqual(denied.status_code, 403, denied.text)
        self.assertEqual(ContractedService.objects.count(), 1)

    def test_l2_amendment_appends_before_after_history_and_invalid_change_is_atomic(self):
        service = ContractedService.objects.create(
            client=self.client_a, service_name='Web', catalog_service=self.offer, recorded_by=self.actors['L2'],
            commitment_reference='OC-1', scope='Inicial', frequency='mensual',
            effective_start=date(2026, 1, 31), evidence_reference='DOC-1',
        )
        response = self.api.put(
            f'/api/clients/{self.client_a.id}/contracted-services/{service.id}',
            headers=self.tokens['L2'], json=self.payload(commitment_reference='OC-2', scope='Ampliado', impact_assessment='Sin pagos ni trabajos anteriores que deban ajustarse'),
        )
        self.assertEqual(response.status_code, 200, response.text)
        history = ContractedServiceHistory.objects.get(service=service)
        self.assertEqual(history.before['scope'], 'Inicial')
        self.assertEqual(history.after['scope'], 'Ampliado')
        l3_history = self.api.get(
            f'/api/clients/{self.client_a.id}/contracted-services', headers=self.tokens['L3'],
        ).json()[0]['history']
        self.assertEqual(l3_history[-1]['before']['scope'], 'Inicial')
        self.assertNotIn('agreed_amount', l3_history[-1]['after'])
        self.assertIsNone(l3_history[-1]['impact_assessment'])
        prior_count = ContractedServiceHistory.objects.count()
        denied = self.api.put(
            f'/api/clients/{self.client_a.id}/contracted-services/{service.id}',
            headers=self.tokens['L3'], json=self.payload(scope='Alteración no autorizada'),
        )
        self.assertEqual(denied.status_code, 403)
        service.refresh_from_db()
        self.assertEqual(service.scope, 'Ampliado')
        self.assertEqual(ContractedServiceHistory.objects.count(), prior_count)

    def test_recurring_due_date_uses_original_anchor_and_one_time_has_none(self):
        monthly = ContractedService(effective_start=date(2026, 1, 31), frequency='mensual')
        self.assertEqual(service_next_due_date(monthly, date(2026, 2, 28)), date(2026, 3, 31))
        self.assertEqual(service_next_due_date(monthly, date(2026, 3, 30)), date(2026, 3, 31))
        annual = ContractedService(effective_start=date(2024, 2, 29), frequency='anual')
        self.assertEqual(service_next_due_date(annual, date(2025, 2, 28)), date(2026, 2, 28))
        single = ContractedService(effective_start=date(2026, 1, 1), frequency='unica')
        self.assertIsNone(service_next_due_date(single, date(2026, 1, 1)))
        missing_anchor = ContractedService(effective_start=None, frequency='mensual')
        self.assertIsNone(service_next_due_date(missing_anchor, date(2026, 1, 1)))

    def test_l3_links_only_same_client_and_service_can_have_one_active_project(self):
        service = ContractedService.objects.create(
            client=self.client_a, service_name='Web', catalog_service=self.offer, recorded_by=self.actors['L2'],
            commitment_reference='OC-2', scope='Web', frequency='anual', evidence_reference='DOC-2',
        )
        body = {'service_id': service.id, 'reason': 'Alcance relacionado'}
        mismatch = self.api.post(
            f'/api/projects/{self.project_b.id}/contracted-services', headers=self.tokens['L3'], json=body,
        )
        self.assertEqual(mismatch.status_code, 409, mismatch.text)
        linked = self.api.post(
            f'/api/projects/{self.project_a.id}/contracted-services', headers=self.tokens['L3'], json=body,
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        service.scope = 'Alcance modificado posteriormente'
        service.save(update_fields=['scope'])
        linked_context = self.api.get(
            f'/api/projects/{self.project_a.id}/contracted-services', headers=self.tokens['L3'],
        )
        self.assertEqual(linked_context.status_code, 200, linked_context.text)
        self.assertEqual(linked_context.json()[0]['scope'], 'Web')
        duplicate = self.api.post(
            f'/api/projects/{self.project_a.id}/contracted-services', headers=self.tokens['L3'], json=body,
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(ProjectContractedService.objects.filter(service=service, unlinked_at__isnull=True).count(), 1)

    def test_l3_unlink_preserves_history_and_requires_impact_free_project(self):
        service = ContractedService.objects.create(
            client=self.client_a, service_name='Web', catalog_service=self.offer, recorded_by=self.actors['L2'],
            commitment_reference='OC-3', scope='Web', frequency='unica', evidence_reference='DOC-3',
        )
        link = ProjectContractedService.objects.create(
            project=self.project_a, service=service, linked_by=self.actors['L3'], link_reason='Alta inicial',
        )
        body = {'service_id': service.id, 'reason': 'Corrección de asociación'}
        response = self.api.post(
            f'/api/projects/{self.project_a.id}/contracted-services/{link.id}/withdrawal',
            headers=self.tokens['L3'], json=body,
        )
        self.assertEqual(response.status_code, 200, response.text)
        link.refresh_from_db()
        self.assertIsNotNone(link.unlinked_at)
        self.assertEqual(link.link_reason, 'Alta inicial')
        self.assertEqual(link.unlink_reason, 'Corrección de asociación')

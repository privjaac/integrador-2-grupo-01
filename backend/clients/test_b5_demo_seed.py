import secrets

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from clients.management.commands.bootstrap_elisa import DEFAULT_ROLES
from clients.models import (
    Client,
    Collaborator,
    CommercialPaymentNotice,
    ContractedService,
    CustomerPayment,
    DocumentedPaymentDue,
    InternalNotification,
    OrganizationalSubstitution,
    Project,
    ProjectCancellationEvent,
    ProjectCoordination,
    ProjectDelivery,
    ProjectDeliveryAuthorization,
    ProjectDeliveryTechnicalReview,
    ProjectDeliveryTransition,
    ProjectEvent,
    Role,
    Task,
    WebCatalog,
    WebFeature,
)


class SeedElisaB5ScenarioTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.roles = {
            level: Role.objects.create(name=name, level=level, description=description)
            for level, name, description in DEFAULT_ROLES
        }
        original_catalog = WebCatalog.objects.create(
            name='Catálogo histórico', base_price_rent='80.00', base_price_sale='800.00',
        )
        self.original_client = Client.objects.create(
            name='Cliente histórico', document_number='ORIGINAL-001',
            web_type=original_catalog,
        )
        self.original_user = Collaborator.objects.create(
            first_name='Original', last_name='L1', document_number='ORIGINAL-USER-001',
            email='original@example.invalid', username='original-l1',
            password_hash='unchanged-hash', role=self.roles['L1'], cupe='ELO-ORIGINAL',
        )

    def run_seed(self):
        call_command(
            'seed_elisa_b5_scenarios',
            expected_database_name=':memory:',
            confirm_demo_database=True,
            verbosity=0,
        )

    def test_seed_preserves_original_records_and_is_idempotent(self):
        self.run_seed()
        first = self.counts()
        self.run_seed()
        self.assertEqual(self.counts(), first)

        self.original_client.refresh_from_db()
        self.original_user.refresh_from_db()
        self.assertEqual(self.original_client.name, 'Cliente histórico')
        self.assertEqual(self.original_user.password_hash, 'unchanged-hash')
        self.assertEqual(Role.objects.count(), 5)
        self.assertEqual(Collaborator.objects.filter(username__startswith='demo-b5-').count(), 6)
        self.assertEqual(Project.objects.filter(name__startswith='DEMO B5').count(), 4)
        self.assertEqual(Task.objects.filter(title__startswith='DEMO').count(), 2)
        self.assertEqual(ContractedService.objects.filter(commitment_reference__startswith='DEMO-B5').count(), 2)
        self.assertEqual(DocumentedPaymentDue.objects.filter(obligation_reference__startswith='DEMO-B5').count(), 1)
        self.assertEqual(CommercialPaymentNotice.objects.filter(source_key__startswith='demo-b5').count(), 1)
        self.assertEqual(CustomerPayment.objects.filter(reference__startswith='DEMO-B5').count(), 1)
        self.assertEqual(InternalNotification.objects.filter(source_key__startswith='demo-b5').count(), 2)
        self.assertEqual(OrganizationalSubstitution.objects.filter(is_active=True).count(), 1)
        self.assertEqual(ProjectCancellationEvent.objects.filter(event_type='efectiva').count(), 1)
        self.assertEqual(ProjectCoordination.objects.filter(is_active=True).count(), 4)

        delivery_project = Project.objects.get(name='DEMO B5 · Validación y entrega')
        ready_event = ProjectEvent.objects.get(
            project=delivery_project, event_type='listo_para_entrega',
        )
        self.assertIsNotNone(ready_event.technical_evaluation_id)
        self.assertIsNotNone(ready_event.delivery_authorization_id)
        evaluation = ready_event.technical_evaluation
        from api.routers.projects import current_task_snapshot
        current_snapshot, _ = current_task_snapshot(delivery_project.pk)
        self.assertEqual(evaluation.task_snapshot, current_snapshot)
        self.assertTrue(evaluation.ordinary_close_valid)
        self.assertEqual(ProjectDeliveryAuthorization.objects.filter(project=delivery_project).count(), 1)
        delivery = ProjectDelivery.objects.get(project=delivery_project)
        self.assertGreaterEqual(delivery.occurred_at, ready_event.occurred_at)
        self.assertEqual(delivery.preparation_authorization_id, ready_event.delivery_authorization_id)
        self.assertFalse(ProjectDeliveryTransition.objects.filter(delivery=delivery).exists())
        self.assertEqual(
            ProjectDeliveryTechnicalReview.objects.get(project=delivery_project).technical_evaluation_id,
            evaluation.pk,
        )

    @staticmethod
    def counts():
        return {
            model.__name__: model.objects.count()
            for model in (
                Role, Collaborator, WebCatalog, WebFeature, Client, Project,
                ProjectCoordination, Task, ContractedService, DocumentedPaymentDue,
                CommercialPaymentNotice, CustomerPayment, InternalNotification,
                OrganizationalSubstitution, ProjectCancellationEvent,
            )
        }

    def test_expected_database_name_must_match_even_for_memory_sqlite(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command(
                'seed_elisa_b5_scenarios',
                expected_database_name='wrong-name',
                confirm_demo_database=True,
                verbosity=0,
            )
        self.assertEqual(Project.objects.count(), 0)

    def test_demo_password_is_read_hidden_and_only_hash_is_persisted(self):
        from unittest.mock import patch

        from api.routers.auth import verify_password

        self.run_seed()
        password = secrets.token_urlsafe(24)
        with patch(
            'clients.management.commands.set_demo_password.getpass.getpass',
            side_effect=[password, password],
        ):
            call_command(
                'set_demo_password', username='demo-b5-l3',
                expected_database_name=':memory:', verbosity=0,
            )
        account = Collaborator.objects.get(username='demo-b5-l3')
        self.assertNotEqual(account.password_hash, password)
        self.assertTrue(verify_password(password, account.password_hash))

    def test_password_command_accepts_only_the_exact_local_staging_identity(self):
        from unittest.mock import MagicMock

        from clients.management.commands.set_demo_password import assert_local_demo_database

        for database_name in ('elisa_b5_demo_20261028', 'elisa_b5_staging'):
            with self.subTest(database_name=database_name):
                connection = MagicMock()
                connection.vendor = 'postgresql'
                connection.settings_dict = {
                    'NAME': database_name,
                    'HOST': '127.0.0.1',
                }
                connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    database_name, '18.6', 5433, 'postgres',
                )

                self.assertIsNone(
                    assert_local_demo_database(connection, database_name)
                )

    def test_password_command_rejects_an_unlisted_database_name(self):
        from unittest.mock import MagicMock

        from clients.management.commands.set_demo_password import assert_local_demo_database

        connection = MagicMock()
        connection.vendor = 'postgresql'
        connection.settings_dict = {
            'NAME': 'elisa_b5_staging_copy',
            'HOST': '127.0.0.1',
        }

        with self.assertRaises(CommandError):
            assert_local_demo_database(connection, 'elisa_b5_staging_copy')

    def test_password_command_rejects_staging_identity_mismatch(self):
        from unittest.mock import MagicMock

        from clients.management.commands.set_demo_password import assert_local_demo_database

        connection = MagicMock()
        connection.vendor = 'postgresql'
        connection.settings_dict = {
            'NAME': 'elisa_b5_staging',
            'HOST': '127.0.0.1',
        }
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            'elisa_b5_staging', '18.6', 5432, 'postgres',
        )

        with self.assertRaises(CommandError):
            assert_local_demo_database(connection, 'elisa_b5_staging')

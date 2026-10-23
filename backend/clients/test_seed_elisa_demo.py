import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import TransactionTestCase

from clients.models import (
    Client,
    ClientFeature,
    Collaborator,
    Role,
    WebCatalog,
    WebFeature,
)


class SeedElisaDemoTests(TransactionTestCase):
    def run_seed(self, **options):
        defaults = {
            'expected_database_name': connections['default'].settings_dict['NAME'],
            'confirm_demo_database': True,
            'verbosity': 0,
        }
        call_command('seed_elisa_demo', **{**defaults, **options})

    def test_confirmation_and_expected_database_name_are_required(self):
        with self.assertRaisesMessage(CommandError, '--confirm-demo-database'):
            self.run_seed(confirm_demo_database=False)
        with self.assertRaisesMessage(CommandError, 'no coincide'):
            self.run_seed(expected_database_name='otra-base')

        self.assertEqual(WebCatalog.objects.count(), 0)

    def test_seed_creates_fictional_data_and_expected_relationships(self):
        self.run_seed()

        self.assertEqual(WebCatalog.objects.count(), 3)
        self.assertEqual(WebFeature.objects.count(), 3)
        self.assertEqual(Client.objects.count(), 3)
        self.assertEqual(ClientFeature.objects.count(), 5)
        self.assertEqual(Collaborator.objects.count(), 0)
        self.assertEqual(Role.objects.count(), 0)

        global_feature = WebFeature.objects.get(name='DEMO · Soporte prioritario')
        self.assertEqual(global_feature.web_types.count(), 0)
        booking_feature = WebFeature.objects.get(name='DEMO · Reservas en línea')
        self.assertEqual(
            list(booking_feature.web_types.values_list('name', flat=True)),
            ['DEMO · Reservas'],
        )
        client = Client.objects.get(document_number='00000003')
        self.assertEqual(client.features.count(), 2)
        self.assertTrue(client.email.endswith('@example.invalid'))
        self.assertEqual(client.created_by_id, None)
        self.assertEqual(
            set(WebFeature.objects.values_list('name', flat=True)),
            {
                'DEMO · Catálogo avanzado',
                'DEMO · Reservas en línea',
                'DEMO · Soporte prioritario',
            },
        )

    def test_second_run_is_idempotent_and_keeps_primary_keys_and_links(self):
        self.run_seed()
        before = {
            'catalogs': list(WebCatalog.objects.order_by('pk').values_list('pk', 'name')),
            'features': list(WebFeature.objects.order_by('pk').values_list('pk', 'name')),
            'clients': list(Client.objects.order_by('pk').values_list('pk', 'document_number')),
            'client_features': list(
                ClientFeature.objects.order_by('pk').values_list(
                    'pk', 'client_id', 'feature_id',
                )
            ),
            'feature_types': list(
                WebFeature.web_types.through.objects.order_by('pk').values_list(
                    'pk', 'webcatalog_id', 'webfeature_id',
                )
            ),
        }

        self.run_seed()

        after = {
            'catalogs': list(WebCatalog.objects.order_by('pk').values_list('pk', 'name')),
            'features': list(WebFeature.objects.order_by('pk').values_list('pk', 'name')),
            'clients': list(Client.objects.order_by('pk').values_list('pk', 'document_number')),
            'client_features': list(
                ClientFeature.objects.order_by('pk').values_list(
                    'pk', 'client_id', 'feature_id',
                )
            ),
            'feature_types': list(
                WebFeature.web_types.through.objects.order_by('pk').values_list(
                    'pk', 'webcatalog_id', 'webfeature_id',
                )
            ),
        }
        self.assertEqual(after, before)

    def test_rejects_non_demo_records_without_modifying_them(self):
        catalog = WebCatalog.objects.create(
            name='Catálogo preexistente',
            base_price_rent='75.00',
            base_price_sale='750.00',
        )
        client = Client.objects.create(
            name='Registro preexistente',
            document_number='TEST-CLIENT-001',
            web_type=catalog,
            notes='Debe permanecer intacto.',
        )

        with self.assertRaisesMessage(CommandError, 'ajenos al conjunto demo'):
            self.run_seed()

        client.refresh_from_db()
        self.assertEqual(client.name, 'Registro preexistente')
        self.assertEqual(client.notes, 'Debe permanecer intacto.')
        self.assertEqual(WebCatalog.objects.count(), 1)
        self.assertEqual(WebFeature.objects.count(), 0)
        self.assertEqual(Client.objects.count(), 1)

    def test_preserves_bootstrap_roles_and_initial_superadmin(self):
        from clients.management.commands.bootstrap_elisa import DEFAULT_ROLES

        roles = {
            level: Role.objects.create(
                level=level, name=name, description=description,
            )
            for level, name, description in DEFAULT_ROLES
        }
        admin = Collaborator.objects.create(
            first_name='DEMO',
            last_name='Admin inicial',
            document_number='00000000',
            email='demo-admin@example.invalid',
            username='demo-admin',
            password_hash='',
            role=roles['L1'],
            cupe='ELO-00000000',
        )

        self.run_seed()

        admin.refresh_from_db()
        self.assertEqual(admin.username, 'demo-admin')
        self.assertEqual(admin.password_hash, '')
        self.assertEqual(Role.objects.count(), 5)
        self.assertEqual(Collaborator.objects.count(), 1)
        self.assertEqual(WebCatalog.objects.count(), 3)

    def test_conflicting_seed_record_or_relationship_is_not_overwritten(self):
        self.run_seed()
        feature = WebFeature.objects.get(name='DEMO · Reservas en línea')
        feature.web_types.clear()

        with self.assertRaisesMessage(CommandError, 'Conflicto en relaciones'):
            self.run_seed()

        self.assertEqual(feature.web_types.count(), 0)
        self.assertEqual(Client.objects.count(), 3)
        self.assertEqual(ClientFeature.objects.count(), 5)

    @patch.dict(os.environ, {'RENDER': 'true'})
    def test_refuses_render_even_with_explicit_confirmation(self):
        with self.assertRaisesMessage(CommandError, 'deshabilitada en Render'):
            self.run_seed()

        self.assertEqual(WebCatalog.objects.count(), 0)

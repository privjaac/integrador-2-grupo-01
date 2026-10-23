"""Carga un conjunto ficticio y repetible para demostrar ELISA localmente."""

import os
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections, transaction

from clients.management.commands.bootstrap_elisa import DEFAULT_ROLES
from clients.models import (
    Client,
    ClientFeature,
    Collaborator,
    CupeLog,
    Role,
    WebCatalog,
    WebFeature,
)


CATALOG_DATA = (
    {
        'name': 'DEMO · Tienda virtual',
        'base_price_rent': Decimal('49.00'),
        'base_price_sale': Decimal('499.00'),
    },
    {
        'name': 'DEMO · Sitio corporativo',
        'base_price_rent': Decimal('59.00'),
        'base_price_sale': Decimal('599.00'),
    },
    {
        'name': 'DEMO · Reservas',
        'base_price_rent': Decimal('69.00'),
        'base_price_sale': Decimal('699.00'),
    },
)

FEATURE_DATA = (
    {
        'name': 'DEMO · Catálogo avanzado',
        'extra_price': Decimal('20.00'),
        'web_types': ('DEMO · Tienda virtual',),
    },
    {
        'name': 'DEMO · Reservas en línea',
        'extra_price': Decimal('25.00'),
        'web_types': ('DEMO · Reservas',),
    },
    {
        'name': 'DEMO · Soporte prioritario',
        'extra_price': Decimal('15.00'),
        'web_types': (),
    },
)

CLIENT_DATA = (
    {
        'cupe': 'CLI-99000001',
        'name': 'DEMO · Café Aurora',
        'document_type': 'DNI',
        'document_number': '00000001',
        'email': 'demo001@example.invalid',
        'web_type': 'DEMO · Tienda virtual',
        'plan': 'alquiler',
        'status': 'desarrollo',
        'base_price': Decimal('49.00'),
        'initial_payment': Decimal('49.00'),
        'extra_price': Decimal('20.00'),
        'total_price': Decimal('69.00'),
        'registration_date': date(2026, 10, 1),
        'delivery_date': None,
        'next_payment_date': None,
        'payment_frequency': 'mensual',
        'domain_price': Decimal('0.00'),
        'notes': 'Registro ficticio reservado para demostraciones locales.',
        'features': ('DEMO · Catálogo avanzado', 'DEMO · Soporte prioritario'),
    },
    {
        'cupe': 'CLI-99000002',
        'name': 'DEMO · Estudio Horizonte',
        'document_type': 'DNI',
        'document_number': '00000002',
        'email': 'demo002@example.invalid',
        'web_type': 'DEMO · Sitio corporativo',
        'plan': 'alquiler',
        'status': 'activo',
        'base_price': Decimal('59.00'),
        'initial_payment': Decimal('59.00'),
        'extra_price': Decimal('15.00'),
        'total_price': Decimal('74.00'),
        'registration_date': date(2026, 7, 20),
        'delivery_date': date(2026, 8, 10),
        'next_payment_date': date(2026, 11, 10),
        'payment_frequency': 'mensual',
        'domain_price': Decimal('0.00'),
        'notes': 'Registro ficticio reservado para demostraciones locales.',
        'features': ('DEMO · Soporte prioritario',),
    },
    {
        'cupe': 'CLI-99000003',
        'name': 'DEMO · Taller de Reservas',
        'document_type': 'DNI',
        'document_number': '00000003',
        'email': 'demo003@example.invalid',
        'web_type': 'DEMO · Reservas',
        'plan': 'venta',
        'status': 'inactivo',
        'base_price': Decimal('699.00'),
        'initial_payment': Decimal('699.00'),
        'extra_price': Decimal('40.00'),
        'total_price': Decimal('739.00'),
        'registration_date': date(2025, 9, 20),
        'delivery_date': date(2025, 10, 5),
        'next_payment_date': date(2026, 9, 20),
        'payment_frequency': 'anual',
        'domain_price': Decimal('0.00'),
        'notes': 'Registro ficticio reservado para demostraciones locales.',
        'features': ('DEMO · Reservas en línea', 'DEMO · Soporte prioritario'),
    },
)

DATABASE_ALIAS = 'default'
BOOTSTRAP_CUPE = 'ELO-00000000'


class Command(BaseCommand):
    help = (
        'Carga datos ficticios en una BD local aislada. Requiere confirmar '
        'el nombre exacto de la base de demostración.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--expected-database-name',
            required=True,
            help='Nombre exacto configurado para la base de demostración.',
        )
        parser.add_argument(
            '--confirm-demo-database',
            action='store_true',
            help='Confirma que la base configurada es local y exclusiva para demo.',
        )

    def handle(self, *args, **options):
        if not options['confirm_demo_database']:
            raise CommandError(
                'Confirma explícitamente la base con --confirm-demo-database.'
            )

        self._assert_isolated_database(options['expected_database_name'])

        try:
            with transaction.atomic(using=DATABASE_ALIAS):
                catalog, features, clients = self._seed()
        except DatabaseError as exc:
            raise CommandError(
                'No se completó la carga; la transacción fue revertida. '
                'Verifica la conexión local y que las migraciones estén aplicadas.'
            ) from exc

        self.stdout.write(self.style.SUCCESS(
            'Datos demo listos: '
            f'{catalog} tipos web, {features} funcionalidades y '
            f'{clients} clientes creados; registros ya existentes compatibles '
            'se conservaron.'
        ))

    def _assert_isolated_database(self, expected_name):
        connection = connections[DATABASE_ALIAS]
        configured_name = str(connection.settings_dict.get('NAME', ''))
        if not expected_name or configured_name != expected_name:
            raise CommandError(
                'El nombre esperado no coincide con la base configurada.'
            )

        if any(
            name in os.environ
            for name in ('RENDER', 'RENDER_SERVICE_ID', 'RENDER_INSTANCE_ID')
        ):
            raise CommandError('La carga demo está deshabilitada en Render.')

        if connection.vendor == 'sqlite':
            is_memory_database = (
                configured_name == ':memory:'
                or (
                    configured_name.startswith('file:')
                    and 'mode=memory' in configured_name
                )
            )
            if not is_memory_database:
                raise CommandError(
                    'SQLite solo se permite en memoria para pruebas aisladas.'
                )
            return

        if connection.vendor != 'postgresql':
            raise CommandError(
                'La carga solo admite PostgreSQL local o SQLite en memoria.'
            )

        host = (connection.settings_dict.get('HOST') or '').strip().lower()
        if host not in ('', 'localhost', '127.0.0.1', '::1'):
            raise CommandError(
                'La carga demo solo se permite contra un PostgreSQL local.'
            )

        pg_host = os.getenv('PGHOST', '').strip().lower()
        if pg_host and pg_host not in ('localhost', '127.0.0.1', '::1'):
            raise CommandError(
                'La configuración libpq indica un host no local; carga rechazada.'
            )
        pg_hostaddr = os.getenv('PGHOSTADDR', '').strip().lower()
        if pg_hostaddr and pg_hostaddr not in ('127.0.0.1', '::1'):
            raise CommandError(
                'La dirección libpq indica un destino no local; carga rechazada.'
            )
        if os.getenv('PGSERVICE'):
            raise CommandError(
                'No se admite PGSERVICE para evitar destinos PostgreSQL indirectos.'
            )

    def _seed(self):
        using = DATABASE_ALIAS
        self._validate_existing_data()

        created_catalogs = {}
        for item in CATALOG_DATA:
            values = {key: value for key, value in item.items() if key != 'name'}
            catalog, created = WebCatalog.objects.using(using).get_or_create(
                name=item['name'], defaults=values,
            )
            created_catalogs[item['name']] = created

        catalogs = {
            item['name']: WebCatalog.objects.using(using).get(name=item['name'])
            for item in CATALOG_DATA
        }

        created_features = {}
        for item in FEATURE_DATA:
            feature, created = WebFeature.objects.using(using).get_or_create(
                name=item['name'],
                defaults={
                    'extra_price': item['extra_price'],
                    'is_active': True,
                },
            )
            created_features[item['name']] = created
            expected_types = {
                catalogs[name].pk for name in item['web_types']
            }
            if created:
                feature.web_types.add(*(catalogs[name] for name in item['web_types']))
            elif set(feature.web_types.using(using).values_list('pk', flat=True)) != expected_types:
                raise CommandError(
                    f'Conflicto en relaciones de la funcionalidad demo "{item["name"]}".'
                )

        features = {
            item['name']: WebFeature.objects.using(using).get(name=item['name'])
            for item in FEATURE_DATA
        }

        created_clients = {}
        for item in CLIENT_DATA:
            values = {
                key: value for key, value in item.items()
                if key not in ('document_number', 'web_type', 'features')
            }
            client, created = Client.objects.using(using).get_or_create(
                document_number=item['document_number'],
                defaults={**values, 'web_type': catalogs[item['web_type']]},
            )
            created_clients[item['document_number']] = created
            expected_features = {
                features[name].pk for name in item['features']
            }
            actual_features = set(
                ClientFeature.objects.using(using)
                .filter(client_id=client.pk)
                .values_list('feature_id', flat=True)
            )
            if created:
                ClientFeature.objects.using(using).bulk_create([
                    ClientFeature(client=client, feature=features[name])
                    for name in item['features']
                ])
            elif actual_features != expected_features:
                raise CommandError(
                    f'Conflicto en relaciones del cliente demo "{item["name"]}".'
                )

        return (
            sum(created_catalogs.values()),
            sum(created_features.values()),
            sum(created_clients.values()),
        )

    def _validate_existing_data(self):
        """Rechaza datos fuera del conjunto demo y conflictos sin sobrescribirlos."""
        using = DATABASE_ALIAS
        self._validate_bootstrap_baseline()

        expected_catalogs = {item['name']: item for item in CATALOG_DATA}
        existing_catalogs = {
            row.name: row for row in WebCatalog.objects.using(using).all()
        }
        self._reject_unrecognized(existing_catalogs, expected_catalogs, 'catálogo')
        for name, row in existing_catalogs.items():
            expected = expected_catalogs[name]
            if any(getattr(row, key) != expected[key] for key in (
                'base_price_rent', 'base_price_sale',
            )) or not row.is_active:
                raise CommandError(f'Conflicto con el tipo web demo "{name}".')

        expected_features = {item['name']: item for item in FEATURE_DATA}
        existing_features = {
            row.name: row for row in WebFeature.objects.using(using).all()
        }
        self._reject_unrecognized(existing_features, expected_features, 'funcionalidad')
        catalog_ids = {
            row.name: row.pk for row in WebCatalog.objects.using(using).all()
        }
        for name, row in existing_features.items():
            expected = expected_features[name]
            if row.extra_price != expected['extra_price'] or not row.is_active:
                raise CommandError(f'Conflicto con la funcionalidad demo "{name}".')
            expected_types = {catalog_ids[type_name] for type_name in expected['web_types']
                              if type_name in catalog_ids}
            actual_types = set(row.web_types.using(using).values_list('pk', flat=True))
            if len(expected_types) != len(expected['web_types']) or actual_types != expected_types:
                raise CommandError(
                    f'Conflicto en relaciones de la funcionalidad demo "{name}".'
                )

        expected_clients = {item['document_number']: item for item in CLIENT_DATA}
        existing_clients = {
            row.document_number: row for row in Client.objects.using(using).all()
        }
        self._reject_unrecognized(existing_clients, expected_clients, 'cliente')
        for document_number, row in existing_clients.items():
            expected = expected_clients[document_number]
            scalar_fields = (
                'cupe', 'name', 'document_type', 'email', 'plan', 'status',
                'base_price', 'initial_payment', 'extra_price', 'total_price',
                'registration_date', 'delivery_date', 'next_payment_date',
                'payment_frequency', 'domain_price', 'notes',
            )
            if any(getattr(row, key) != expected[key] for key in scalar_fields):
                raise CommandError(
                    f'Conflicto con el cliente demo "{expected["name"]}".'
                )
            expected_type = WebCatalog.objects.using(using).filter(
                name=expected['web_type'],
            ).values_list('pk', flat=True).first()
            if (
                expected_type is None
                or row.web_type_id != expected_type
                or row.created_by_id is not None
            ):
                raise CommandError(
                    f'Conflicto con el cliente demo "{expected["name"]}".'
                )

        expected_links = {
            (client['document_number'], feature_name)
            for client in CLIENT_DATA
            for feature_name in client['features']
        }
        actual_links = set(
            ClientFeature.objects.using(using)
            .values_list('client__document_number', 'feature__name')
        )
        if not actual_links.issubset(expected_links):
            raise CommandError(
                'La base contiene asociaciones cliente-funcionalidad ajenas al conjunto demo.'
            )

        if CupeLog.objects.using(using).exists():
            raise CommandError(
                'La base contiene historial CUPE; la carga demo requiere una base aislada.'
            )

    def _validate_bootstrap_baseline(self):
        using = DATABASE_ALIAS
        expected_roles = {
            level: (name, description)
            for level, name, description in DEFAULT_ROLES
        }
        roles = {
            role.level: (role.name, role.description)
            for role in Role.objects.using(using).all()
        }
        if any(level not in expected_roles for level in roles) or any(
            expected_roles[level] != values for level, values in roles.items()
        ):
            raise CommandError(
                'La base contiene roles ajenos o modificados; carga demo rechazada.'
            )
        if roles and set(roles) != set(expected_roles):
            raise CommandError(
                'La base contiene un conjunto parcial de roles; carga demo rechazada.'
            )

        collaborators = list(Collaborator.objects.using(using).select_related('role'))
        if collaborators and not (
            len(collaborators) == 1
            and collaborators[0].cupe == BOOTSTRAP_CUPE
            and collaborators[0].role_id is not None
            and collaborators[0].role.level == 'L1'
        ):
            raise CommandError(
                'La base contiene colaboradores fuera del bootstrap inicial; '
                'carga demo rechazada.'
            )

    @staticmethod
    def _reject_unrecognized(existing, expected, label):
        unknown = set(existing) - set(expected)
        if unknown:
            raise CommandError(
                f'La base contiene registros de {label} ajenos al conjunto demo; '
                'no se realizaron cambios.'
            )

"""Establece una clave de demostración mediante entrada oculta local."""

import getpass

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from api.routers.auth import hash_password
from clients.models import Collaborator

LOCAL_DEMO_DATABASES = {
    'elisa_b5_demo_20261028',
    'elisa_b5_staging',
}


def assert_local_demo_database(connection, expected_name):
    if (
        connection.vendor != 'postgresql'
        or expected_name not in LOCAL_DEMO_DATABASES
        or connection.settings_dict.get('NAME') != expected_name
        or connection.settings_dict.get('HOST') not in ('127.0.0.1', 'localhost', '::1')
    ):
        raise CommandError(
            'El cambio de contraseña solo admite las bases B5 locales autorizadas.'
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), current_setting('server_version'), "
            'inet_server_port(), current_user'
        )
        identity = cursor.fetchone()
    if identity != (expected_name, '18.6', 5433, 'postgres'):
        raise CommandError('La identidad SQL no coincide con una base B5 local autorizada.')


class Command(BaseCommand):
    help = 'Asigna una contraseña a una cuenta demo B5 sin mostrarla ni guardarla en archivos.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--expected-database-name', required=True)

    def handle(self, *args, **options):
        connection = connections['default']
        expected_name = options['expected_database_name']
        sqlite_name = str(connection.settings_dict.get('NAME') or '')
        is_memory_test = connection.vendor == 'sqlite' and (
            sqlite_name == ':memory:' or 'mode=memory' in sqlite_name
        )
        if is_memory_test:
            if expected_name not in (':memory:', sqlite_name):
                raise CommandError('El nombre de base de prueba debe ser SQLite en memoria.')
        else:
            assert_local_demo_database(connection, expected_name)

        username = options['username']
        if not username.startswith('demo-b5-'):
            raise CommandError('Solo permite modificar cuentas demo-b5-.')
        try:
            collaborator = Collaborator.objects.select_related('role').get(username=username)
        except Collaborator.DoesNotExist as exc:
            raise CommandError('No existe esa cuenta de demostración.') from exc
        if not collaborator.is_active or collaborator.role is None:
            raise CommandError('La cuenta demo debe estar activa y tener un nivel asignado.')
        if collaborator.auth_sessions.filter(revoked_at__isnull=True).exists():
            raise CommandError('Cierra las sesiones demo activas antes de cambiar la contraseña.')

        password = getpass.getpass('Nueva contraseña (mínimo 14 caracteres): ')
        confirmation = getpass.getpass('Repite la nueva contraseña: ')
        if len(password) < 14:
            raise CommandError('La contraseña debe tener al menos 14 caracteres.')
        if password != confirmation:
            raise CommandError('Las contraseñas no coinciden.')

        with transaction.atomic():
            collaborator.password_hash = hash_password(password)
            collaborator.save(update_fields=['password_hash', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(
            f'Contraseña actualizada para {username} ({collaborator.role.level}).'
        ))

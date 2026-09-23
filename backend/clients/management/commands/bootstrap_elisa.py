"""Crea los cinco niveles y la primera cuenta Superadmin."""

import getpass
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.routers.auth import hash_password
from clients.models import Collaborator, Role


DEFAULT_ROLES = (
    ('L1', 'Superadmin', 'Administración del sistema'),
    ('L2', 'Scrum Master', 'Gestión del equipo y proyectos'),
    ('L3', 'Tech Lead', 'Coordinación técnica'),
    ('L4', 'Líder', 'Coordinación de área'),
    ('L5', 'Developer', 'Trabajo de desarrollo'),
)


class Command(BaseCommand):
    help = 'Inicializa roles y la primera cuenta Superadmin de ELISA.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--email', required=True)
        parser.add_argument('--document-number', required=True)
        parser.add_argument('--first-name', default='Admin')
        parser.add_argument('--last-name', default='ELISA')

    def handle(self, *args, **options):
        if Collaborator.objects.filter(role__level='L1').exists():
            raise CommandError('Ya existe una cuenta Superadmin; no se creó otra.')

        password = os.getenv('ELISA_BOOTSTRAP_PASSWORD') or getpass.getpass(
            'Contraseña inicial (mínimo 8 caracteres): '
        )
        if len(password) < 8:
            raise CommandError('La contraseña debe tener al menos 8 caracteres.')

        with transaction.atomic():
            for level, name, description in DEFAULT_ROLES:
                Role.objects.get_or_create(
                    level=level,
                    defaults={'name': name, 'description': description},
                )
            superadmin_role = Role.objects.get(level='L1')
            admin = Collaborator.objects.create(
                username=options['username'],
                email=options['email'],
                document_number=options['document_number'],
                first_name=options['first_name'],
                last_name=options['last_name'],
                role=superadmin_role,
                password_hash=hash_password(password),
                cupe='ELO-00000000',
            )

        self.stdout.write(self.style.SUCCESS(
            f'Roles inicializados y Superadmin {admin.username} creado.'
        ))

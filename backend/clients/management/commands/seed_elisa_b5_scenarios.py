"""Carga escenarios ficticios e idempotentes en la base local B5 aislada."""

import os
import secrets
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections, transaction
from django.utils import timezone

from api.routers.auth import hash_password
from clients.management.commands.seed_elisa_demo import Command as BaseDemoCommand
from clients.models import (
    Client,
    Collaborator,
    CollaboratorPayment,
    CommercialPaymentNotice,
    ContractedService,
    CustomerPayment,
    DocumentedPaymentDue,
    InternalNotification,
    OrganizationalSubstitution,
    Project,
    ProjectCancellation,
    ProjectCancellationEvent,
    ProjectCommercialAuthorization,
    ProjectContractedService,
    ProjectCoordination,
    ProjectDelivery,
    ProjectDeliveryTechnicalReview,
    ProjectEvent,
    ProjectLeadership,
    ProjectResumption,
    ProjectResumptionEvent,
    ProjectTaskClassification,
    ProjectTechnicalEvaluation,
    Role,
    Task,
    TaskComment,
    TaskEvent,
    TeamMembership,
)


EXPECTED_DATABASE = 'elisa_b5_demo_20261028'
INITIAL_DEMO_CLIENTS = ('00000001', '00000002', '00000003')
DEMO_USERS = {
    'L1': ('demo-b5-l1', 'ELO-99000001', 'DEMO-B5-L1'),
    'L2': ('demo-b5-l2', 'ELO-99000002', 'DEMO-B5-L2'),
    'L3': ('demo-b5-l3', 'ELO-99000003', 'DEMO-B5-L3'),
    'L4': ('demo-b5-l4', 'ELO-99000004', 'DEMO-B5-L4'),
    'L5': ('demo-b5-l5', 'ELO-99000005', 'DEMO-B5-L5'),
}
SUBSTITUTE_USER = ('demo-b5-l4-sub', 'ELO-99000006', 'DEMO-B5-L4-SUB')
DB_ALIAS = 'default'


class Command(BaseCommand):
    help = 'Añade escenarios ficticios B5, sin tocar registros históricos.'

    def add_arguments(self, parser):
        parser.add_argument('--expected-database-name', required=True)
        parser.add_argument('--confirm-demo-database', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_demo_database']:
            raise CommandError('Confirma explícitamente la base demo.')
        connection = connections[DB_ALIAS]
        sqlite_name = str(connection.settings_dict.get('NAME') or '')
        is_memory_test = connection.vendor == 'sqlite' and (
            sqlite_name == ':memory:' or 'mode=memory' in sqlite_name
        )
        expected_name = options['expected_database_name']
        if is_memory_test and expected_name not in (':memory:', sqlite_name):
            raise CommandError('El nombre de base de prueba debe ser SQLite en memoria.')
        if not is_memory_test and expected_name != EXPECTED_DATABASE:
            raise CommandError('La carga B5 solo admite la base demo autorizada.')
        if is_memory_test:
            expected_name = sqlite_name or ':memory:'
        BaseDemoCommand()._assert_isolated_database(expected_name)

        if connection.vendor != 'postgresql':
            if not is_memory_test:
                raise CommandError('La preparación B5 requiere PostgreSQL local.')
        else:
            if connection.settings_dict.get('HOST') not in ('127.0.0.1', 'localhost', '::1'):
                raise CommandError('El servidor configurado no es local.')
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_setting('server_version'), "
                    'inet_server_port(), current_user'
                )
                identity = cursor.fetchone()
            if identity != (EXPECTED_DATABASE, '18.6', 5433, 'postgres'):
                raise CommandError('La identidad SQL no coincide con el destino B5 autorizado.')

        call_command(
            'seed_elisa_demo',
            expected_database_name=expected_name,
            confirm_demo_database=True,
            preserve_existing_records=True,
            verbosity=0,
        )

        try:
            with transaction.atomic(using=DB_ALIAS):
                actors = self._ensure_demo_users()
                clients = self._get_demo_clients()
                self._assign_commercial_responsible(clients, actors['L2'])
                service, due = self._ensure_commercial_records(clients, actors)
                projects = self._ensure_projects(clients, service, actors)
        except DatabaseError as exc:
            raise CommandError(
                'No se completó la carga B5; se revirtió la transacción de escenarios.'
            ) from exc
        counts = self._scenario_counts(projects, service, due)

        self.stdout.write(self.style.SUCCESS(
            'Escenarios B5 listos (idempotentes): '
            f'{len(actors)} cuentas, {len(projects)} proyectos; '
            f'{counts["tasks"]} tareas, {counts["payments"]} pagos, '
            f'{counts["notices"]} avisos comerciales e '
            f'{counts["notifications"]} notificaciones internas.'
        ))

    def _ensure_demo_users(self):
        actors = {}
        for level, (username, cupe, document_number) in DEMO_USERS.items():
            role = Role.objects.using(DB_ALIAS).get(level=level, is_active=True)
            actor, created = Collaborator.objects.using(DB_ALIAS).get_or_create(
                username=username,
                defaults={
                    'first_name': f'Demo {level}',
                    'last_name': 'B5',
                    'document_type': 'DNI',
                    'document_number': document_number,
                    'email': f'{username}@example.invalid',
                    'username': username,
                    'password_hash': hash_password(secrets.token_urlsafe(48)),
                    'role': role,
                    'area': 'Demostración local',
                    'city': 'Lima',
                    'is_active': True,
                    'cupe': cupe,
                },
            )
            self._assert_demo_user(actor, level, document_number, cupe)
            actors[level] = actor

        username, cupe, document_number = SUBSTITUTE_USER
        role = Role.objects.using(DB_ALIAS).get(level='L4', is_active=True)
        substitute, _ = Collaborator.objects.using(DB_ALIAS).get_or_create(
            username=username,
            defaults={
                'first_name': 'Demo L4', 'last_name': 'Sustituto B5',
                'document_type': 'DNI', 'document_number': document_number,
                'email': f'{username}@example.invalid', 'username': username,
                'password_hash': hash_password(secrets.token_urlsafe(48)),
                'role': role, 'area': 'Demostración local', 'city': 'Lima',
                'is_active': True, 'cupe': cupe,
            },
        )
        self._assert_demo_user(substitute, 'L4', document_number, cupe)
        actors['L4_SUB'] = substitute
        return actors

    @staticmethod
    def _assert_demo_user(actor, level, document_number, cupe):
        if (
            actor.role_id is None or actor.role.level != level or not actor.is_active
            or actor.document_number != document_number or actor.cupe != cupe
            or actor.email != f'{actor.username}@example.invalid'
        ):
            raise CommandError(
                f'La cuenta {actor.username} existe con datos incompatibles; no se alteró.'
            )

    def _get_demo_clients(self):
        clients = {}
        for document_number in INITIAL_DEMO_CLIENTS:
            try:
                clients[document_number] = Client.objects.using(DB_ALIAS).get(
                    document_number=document_number,
                )
            except Client.DoesNotExist as exc:
                raise CommandError('Falta un cliente ficticio del conjunto demo inicial.') from exc
        return clients

    def _assign_commercial_responsible(self, clients, l2):
        for client in clients.values():
            if client.commercial_responsible_id is None:
                client.commercial_responsible = l2
                client.save(using=DB_ALIAS, update_fields=['commercial_responsible'])
            elif client.commercial_responsible_id != l2.pk:
                raise CommandError(
                    'Un cliente demo ya tiene otro responsable comercial; no se modificó.'
                )

    def _ensure_commercial_records(self, clients, actors):
        client = clients['00000001']
        # Fixed demo reference date keeps due records and payments idempotent
        # when the loader is rerun on a later day.
        today = date(2026, 10, 28)
        service_ref = 'DEMO-B5-COMPROMISO-001'
        service, _ = ContractedService.objects.using(DB_ALIAS).get_or_create(
            client=client,
            commitment_reference=service_ref,
            defaults={
                'service_name': 'DEMO · Implementación de tienda virtual',
                'catalog_service': client.web_type,
                'scope': 'Diseño, configuración y puesta en marcha de tienda ficticia.',
                'agreed_amount': Decimal('1200.00'), 'currency': 'PEN',
                'frequency': 'unica', 'effective_start': today - timedelta(days=30),
                'contracted_duration': 'Entrega por alcance documentado',
                'documented_expiration': None,
                'terms': 'Compromiso ficticio para pruebas locales; sin cobros reales.',
                'evidence_reference': 'DEMO-B5-EVIDENCIA-SERVICIO-001',
                'recorded_by': actors['L2'],
            },
        )
        if service.recorded_by_id != actors['L2'].pk or service.evidence_reference != 'DEMO-B5-EVIDENCIA-SERVICIO-001':
            raise CommandError('El compromiso demo existente no coincide con su referencia.')

        due, _ = DocumentedPaymentDue.objects.using(DB_ALIAS).get_or_create(
            service=service,
            due_date=today + timedelta(days=7),
            obligation_reference='DEMO-B5-OBLIGACION-001',
            defaults={
                'client': client,
                'evidence_reference': 'DEMO-B5-EVIDENCIA-VENCIMIENTO-001',
                'recorded_by': actors['L2'],
            },
        )
        notice, _ = CommercialPaymentNotice.objects.using(DB_ALIAS).get_or_create(
            source_key='demo-b5-commercial-due-001',
            defaults={
                'due': due, 'channel': 'internal', 'anticipation_days': 7,
                'recipient': actors['L2'], 'destination_snapshot': actors['L2'].username,
                'status': 'disponible', 'title': 'DEMO · Vencimiento documentado',
                'message': 'Revisar obligación ficticia de prueba B5.',
                'available_at': timezone.now(),
            },
        )
        if notice.due_id != due.pk or notice.recipient_id != actors['L2'].pk:
            raise CommandError('El aviso comercial demo existente apunta a datos distintos.')

        paid_service_ref = 'DEMO-B5-COMPROMISO-002'
        paid_service, _ = ContractedService.objects.using(DB_ALIAS).get_or_create(
            client=client,
            commitment_reference=paid_service_ref,
            defaults={
                'service_name': 'DEMO · Soporte de sitio corporativo',
                'catalog_service': client.web_type,
                'scope': 'Soporte ficticio para comprobar pagos y vigencias.',
                'agreed_amount': Decimal('180.00'), 'currency': 'PEN',
                'frequency': 'mensual', 'effective_start': today - timedelta(days=10),
                'contracted_duration': 'Periodo mensual documentado',
                'documented_expiration': today + timedelta(days=20),
                'terms': 'Registro ficticio; no implica renovación automática.',
                'evidence_reference': 'DEMO-B5-EVIDENCIA-SERVICIO-002',
                'recorded_by': actors['L2'],
            },
        )
        payment, _ = CustomerPayment.objects.using(DB_ALIAS).get_or_create(
            client=client,
            reference='DEMO-B5-RECIBO-001',
            defaults={
                'service': paid_service, 'amount': Decimal('180.00'), 'currency': 'PEN',
                'effective_date': today - timedelta(days=1),
                'evidence_reference': 'DEMO-B5-EVIDENCIA-PAGO-001',
                'recorded_by': actors['L2'], 'confirmed_by': actors['L1'],
                'confirmed_at': timezone.now(),
                'confirmation_evidence': 'DEMO-B5-CONFIRMACION-PAGO-001',
            },
        )
        if payment.service_id != paid_service.pk or payment.confirmed_by_id != actors['L1'].pk:
            raise CommandError('El pago demo existente no coincide con su servicio o confirmación.')

        collaborator_payment, _ = CollaboratorPayment.objects.using(DB_ALIAS).get_or_create(
            request_key=uuid.uuid5(uuid.NAMESPACE_URL, 'elisa-b5-demo-collaborator-payment-001'),
            defaults={
                'collaborator': actors['L5'], 'payment_date': today - timedelta(days=2),
                'amount': Decimal('150.00'), 'concept': 'DEMO · Hito de desarrollo',
                'observation': 'Movimiento ficticio sin transferencia real.',
                'reference': 'DEMO-B5-PAY-001', 'registered_by': actors['L2'],
            },
        )
        if collaborator_payment.collaborator_id != actors['L5'].pk:
            raise CommandError('El pago demo existente apunta a otro colaborador.')
        return service, due

    def _ensure_projects(self, clients, service, actors):
        start_project = self._project(
            clients['00000001'], 'DEMO B5 · Inicio de proyecto', 'Planificado',
        )
        active_project = self._project(
            clients['00000002'], 'DEMO B5 · Tablero de tareas', 'En ejecución',
        )
        delivery_project = self._project(
            clients['00000002'], 'DEMO B5 · Validación y entrega', 'Listo para entrega',
        )
        resumed_project = self._project(
            clients['00000003'], 'DEMO B5 · Reanudación excepcional', 'Planificado',
        )

        start_auth = self._authorization(start_project, actors['L2'])
        active_auth = self._authorization(active_project, actors['L2'])
        delivery_auth = self._authorization(delivery_project, actors['L2'])
        start_coord = self._coordination(start_project, actors)
        active_coord = self._coordination(active_project, actors)
        delivery_coord = self._coordination(delivery_project, actors)
        resumed_coord = self._coordination(resumed_project, actors)

        ProjectContractedService.objects.using(DB_ALIAS).get_or_create(
            project=start_project, service=service,
            defaults={
                'linked_by': actors['L3'],
                'link_reason': 'Asociación ficticia para demostrar alcance contratado.',
                'commitment_snapshot': {
                    'reference': service.commitment_reference, 'scope': service.scope,
                },
            },
        )
        self._project_event(
            active_project, 'inicio_ejecucion', 'Planificado', 'En ejecución',
            actors['L3'], authorization=active_auth,
        )
        self._project_event(
            delivery_project, 'inicio_ejecucion', 'Planificado', 'En ejecución',
            actors['L3'], authorization=delivery_auth,
        )
        self._ensure_tasks(active_project, delivery_project, active_coord, delivery_coord, actors)
        validation = self._project_event(
            delivery_project, 'ingreso_validacion_tecnica', 'En ejecución',
            'En validación técnica', actors['L3'], authorization=delivery_auth,
        )
        latest_task_event = TaskEvent.objects.using(DB_ALIAS).filter(
            task__project=delivery_project,
        ).order_by('-occurred_at', '-id').first()
        validation_at = (latest_task_event.occurred_at if latest_task_event else timezone.now()) + timedelta(seconds=1)
        ProjectEvent.objects.using(DB_ALIAS).filter(pk=validation.pk).update(occurred_at=validation_at)
        evaluation, _ = ProjectTechnicalEvaluation.objects.using(DB_ALIAS).get_or_create(
            validation_event=validation,
            defaults={
                'project': delivery_project, 'actor': actors['L3'],
                'scope_snapshot': delivery_project.scope, 'satisfactory': True,
                'technical_enablement_status': 'Vigente', 'ordinary_close_valid': True,
                'obligations_compatible': True,
                'result_summary': 'Escenario ficticio: validación técnica satisfactoria.',
                'evidence': 'DEMO-B5-EVIDENCIA-VALIDACION-001',
                'ordinary_close_evidence': 'DEMO-B5-EVIDENCIA-CIERRE-001',
                'obligations_assessment': 'Obligaciones compatibles en datos de demostración.',
                'optional_task_assessments': [], 'validated_versions': ['demo-v1.0'],
                'task_snapshot': [],
            },
        )
        classification = ProjectTaskClassification.objects.using(DB_ALIAS).get(
            project=delivery_project, task__title='DEMO · Validar recorrido de compra', is_current=True,
        )
        finished_task = classification.task
        last_task_event = TaskEvent.objects.using(DB_ALIAS).filter(
            task=finished_task,
        ).order_by('-occurred_at', '-id').first()
        expected_snapshot = [{
            'task_id': finished_task.pk,
            'classification_id': classification.pk,
            'is_mandatory': classification.is_mandatory,
            'status': finished_task.status,
            'is_blocked': finished_task.is_blocked,
            'last_event_id': last_task_event.pk if last_task_event else None,
            'last_event_type': last_task_event.event_type if last_task_event else None,
            'last_event_status': last_task_event.new_status if last_task_event else None,
        }]
        if evaluation.task_snapshot != expected_snapshot:
            ProjectTechnicalEvaluation.objects.using(DB_ALIAS).filter(pk=evaluation.pk).update(
                task_snapshot=expected_snapshot,
                evaluated_at=validation_at + timedelta(seconds=1),
            )
            evaluation.refresh_from_db(using=DB_ALIAS)
        else:
            ProjectTechnicalEvaluation.objects.using(DB_ALIAS).filter(pk=evaluation.pk).update(
                evaluated_at=validation_at + timedelta(seconds=1),
            )
        evaluation.refresh_from_db(using=DB_ALIAS)
        ready_event = self._project_event(
            delivery_project, 'listo_para_entrega', 'En validación técnica',
            'Listo para entrega', actors['L3'], technical_evaluation=evaluation,
            delivery_authorization=self._delivery_auth(delivery_project, actors['L2']),
        )
        ProjectEvent.objects.using(DB_ALIAS).filter(pk=ready_event.pk).update(
            technical_evaluation=evaluation,
            delivery_authorization=self._delivery_auth(delivery_project, actors['L2']),
            occurred_at=evaluation.evaluated_at + timedelta(seconds=1),
        )
        ready_event.refresh_from_db(using=DB_ALIAS)
        review, _ = ProjectDeliveryTechnicalReview.objects.using(DB_ALIAS).get_or_create(
            project=delivery_project, version_reference='demo-v1.0',
            defaults={
                'technical_evaluation': evaluation, 'actor': actors['L3'],
                'satisfactory': True, 'technical_enablement_status': 'Vigente',
                'result_summary': 'Versión de demostración habilitada.',
                'evidence': 'DEMO-B5-EVIDENCIA-VERSION-001',
            },
        )
        ProjectDeliveryTechnicalReview.objects.using(DB_ALIAS).filter(pk=review.pk).update(
            technical_evaluation=evaluation,
            reviewed_at=ready_event.occurred_at + timedelta(seconds=1),
        )
        delivery, _ = ProjectDelivery.objects.using(DB_ALIAS).get_or_create(
            project=delivery_project, version_reference='demo-v1.0',
            defaults={
                'recorded_by': actors['L2'], 'preparation_authorization': self._delivery_auth(delivery_project, actors['L2']),
                'delivery_type': 'parcial', 'scope': 'Entrega parcial ficticia del módulo de catálogo.',
                'scope_within_authorization': True, 'covers_project_scope': False,
                'recipient': 'Contacto ficticio de demostración',
                'delivery_method': 'Presentación local en entorno de demostración',
                'performed_by': 'Equipo DEMO B5',
                'evidence_reference': 'DEMO-B5-CONSTANCIA-ENTREGA-PARCIAL-001',
                'occurred_at': ready_event.occurred_at + timedelta(minutes=1),
            },
        )
        ProjectDelivery.objects.using(DB_ALIAS).filter(pk=delivery.pk).update(
            occurred_at=ready_event.occurred_at + timedelta(minutes=1),
        )
        self._ensure_substitution(active_coord, actors)
        self._ensure_resumption(resumed_project, resumed_coord, actors)
        return [start_project, active_project, delivery_project, resumed_project]

    @staticmethod
    def _project(client, name, status):
        project, _ = Project.objects.using(DB_ALIAS).get_or_create(
            client=client, name=name,
            defaults={
                'objective': f'{name}: escenario ficticio de demostración B5.',
                'scope': 'Alcance sintético delimitado para recorridos visuales.',
                'status': status,
            },
        )
        if project.status != status:
            raise CommandError(f'El proyecto demo {name} tiene un estado incompatible.')
        return project

    @staticmethod
    def _authorization(project, actor):
        authorization, _ = ProjectCommercialAuthorization.objects.using(DB_ALIAS).get_or_create(
            project=project, commitment_reference=f'DEMO-B5-START-{project.pk}',
            defaults={
                'authorized_by': actor, 'effective_at': timezone.now() - timedelta(days=1),
                'authorized_scope': project.scope, 'start_conditions': 'Datos sintéticos completos.',
                'start_conditions_accredited': True,
                'evidence_reference': f'DEMO-B5-AUTORIZACION-INICIO-{project.pk}',
            },
        )
        return authorization

    @staticmethod
    def _coordination(project, actors):
        coordination, _ = ProjectCoordination.objects.using(DB_ALIAS).get_or_create(
            project=project, coordinator=actors['L3'], is_active=True,
            defaults={'assigned_by': actors['L2']},
        )
        if not coordination.is_active:
            raise CommandError('La coordinación demo no está vigente.')
        return coordination

    @staticmethod
    def _project_event(project, event_type, previous, new, actor, authorization=None,
                       technical_evaluation=None, delivery_authorization=None):
        event, _ = ProjectEvent.objects.using(DB_ALIAS).get_or_create(
            project=project, event_type=event_type, new_status=new,
            defaults={
                'actor': actor, 'commercial_authorization': authorization,
                'technical_evaluation': technical_evaluation,
                'delivery_authorization': delivery_authorization,
                'previous_status': previous, 'reason': 'Escenario ficticio B5.',
                'evidence': f'DEMO-B5-{event_type.upper()}',
            },
        )
        return event

    @staticmethod
    def _delivery_auth(project, actor):
        from clients.models import ProjectDeliveryAuthorization
        authorization, _ = ProjectDeliveryAuthorization.objects.using(DB_ALIAS).get_or_create(
            project=project,
            evidence_reference=f'DEMO-B5-AUTORIZACION-ENTREGA-{project.pk}',
            defaults={
                'authorized_by': actor, 'effective_at': timezone.now() - timedelta(hours=2),
                'authorized_scope': project.scope, 'scope_snapshot': project.scope,
                'effectivity_conditions': 'Condiciones ficticias acreditadas.',
                'conditions_accredited': True,
            },
        )
        return authorization

    def _ensure_tasks(self, active_project, delivery_project, active_coord, delivery_coord, actors):
        leadership, _ = ProjectLeadership.objects.using(DB_ALIAS).get_or_create(
            coordination=active_coord, leader=actors['L4'], is_active=True,
            defaults={'designated_by': actors['L3']},
        )
        TeamMembership.objects.using(DB_ALIAS).get_or_create(
            leadership=leadership, developer=actors['L5'], is_active=True,
            defaults={'added_by': actors['L4']},
        )
        now = timezone.now()
        task, _ = Task.objects.using(DB_ALIAS).get_or_create(
            project=active_project, title='DEMO · Integrar catálogo de productos',
            defaults={
                'description': 'Tarea ficticia para asignación, comentarios y avisos.',
                'status': 'En proceso', 'created_by': actors['L3'],
                'responsible': actors['L4'], 'assignee': actors['L5'],
                'assigned_at': now - timedelta(days=1), 'due_at': now + timedelta(days=3),
            },
        )
        self._task_event(task, 'creada', '', 'Pendiente', actors['L3'])
        assignment = self._task_event(
            task, 'asignada', 'Pendiente', 'Asignada', actors['L4'],
            assignee=actors['L5'], responsible=actors['L4'],
        )
        started = self._task_event(task, 'iniciada', 'Asignada', 'En proceso', actors['L5'])
        comment_event = self._task_event(
            task, 'comentario_agregado', 'En proceso', 'En proceso', actors['L5'],
            reason='Comentario ficticio de seguimiento.',
        )
        TaskComment.objects.using(DB_ALIAS).get_or_create(
            event=comment_event,
            defaults={
                'task': task, 'author': actors['L5'],
                'content': 'DEMO: integración iniciada; la revisión visual queda pendiente.',
            },
        )
        InternalNotification.objects.using(DB_ALIAS).get_or_create(
            source_key=f'demo-b5-task-update-{task.pk}',
            defaults={
                'event': comment_event, 'task': task, 'recipient': actors['L3'],
                'notice_type': 'comentario_tarea', 'title': 'DEMO · Comentario de tarea',
                'message': 'Se registró un comentario ficticio en una tarea de demostración.',
            },
        )
        InternalNotification.objects.using(DB_ALIAS).get_or_create(
            source_key=f'demo-b5-task-assigned-{task.pk}',
            defaults={
                'event': assignment, 'task': task, 'recipient': actors['L5'],
                'notice_type': 'asignacion_tarea', 'title': 'DEMO · Tarea asignada',
                'message': 'Tienes una tarea ficticia asignada para el entorno B5.',
            },
        )

        finished, _ = Task.objects.using(DB_ALIAS).get_or_create(
            project=delivery_project, title='DEMO · Validar recorrido de compra',
            defaults={
                'description': 'Tarea obligatoria ficticia para validación técnica.',
                'status': 'Finalizada', 'created_by': actors['L3'],
                'responsible': actors['L4'], 'assignee': actors['L5'],
                'assigned_at': now - timedelta(days=2), 'due_at': now - timedelta(days=1),
            },
        )
        self._task_event(finished, 'creada', '', 'Pendiente', actors['L3'])
        self._task_event(
            finished, 'asignada', 'Pendiente', 'Asignada', actors['L4'],
            assignee=actors['L5'], responsible=actors['L4'],
        )
        self._task_event(finished, 'iniciada', 'Asignada', 'En proceso', actors['L5'])
        self._task_event(
            finished, 'resultado_presentado', 'En proceso', 'En revisión', actors['L5'],
            evidence='DEMO-B5-EVIDENCIA-TAREA-001', result='Recorrido de prueba documentado.',
        )
        self._task_event(
            finished, 'aprobada_revision', 'En revisión', 'Finalizada', actors['L4'],
            evidence='DEMO-B5-APROBACION-TAREA-001',
        )
        ProjectTaskClassification.objects.using(DB_ALIAS).get_or_create(
            task=finished, is_current=True,
            defaults={
                'project': delivery_project, 'actor': actors['L3'], 'is_mandatory': True,
                'scope_snapshot': delivery_project.scope,
                'reason': 'Clasificación ficticia para demostrar evaluación integral.',
            },
        )
        return task, finished

    @staticmethod
    def _task_event(task, event_type, previous, new, actor, assignee=None,
                    responsible=None, evidence='', result='', reason=''):
        event, _ = TaskEvent.objects.using(DB_ALIAS).get_or_create(
            task=task, event_type=event_type, new_status=new, actor=actor,
            defaults={
                'previous_status': previous, 'assignee': assignee,
                'responsible': responsible, 'evidence': evidence,
                'result_text': result, 'reason': reason,
            },
        )
        return event

    def _ensure_substitution(self, coordination, actors):
        leadership, _ = ProjectLeadership.objects.using(DB_ALIAS).get_or_create(
            coordination=coordination, leader=actors['L4'], is_active=True,
            defaults={'designated_by': actors['L3']},
        )
        now = timezone.now()
        substitution, _ = OrganizationalSubstitution.objects.using(DB_ALIAS).get_or_create(
            coordination=coordination, absent_person=actors['L4'], is_active=True,
            defaults={
                'leadership': leadership, 'absent_level': 'L4',
                'substitute': actors['L4_SUB'], 'designated_by': actors['L3'],
                'reason': 'Ausencia ficticia para recorrido visual.',
                'evidence': 'DEMO-B5-CONSTANCIA-SUSTITUCION-001',
                'scope': 'Facultades limitadas al equipo del proyecto demo.',
                'faculties': ['tasks.view', 'tasks.review'],
                'valid_from': now - timedelta(hours=1),
                'valid_until': now + timedelta(days=14),
            },
        )
        if substitution.substitute_id != actors['L4_SUB'].pk:
            raise CommandError('La sustitución demo activa apunta a otra cuenta.')

    def _ensure_resumption(self, project, _coordination, actors):
        cancellation, _ = ProjectCancellation.objects.using(DB_ALIAS).get_or_create(
            project=project, reason='DEMO-B5-CANCELACION-001',
            defaults={
                'opened_by': actors['L2'], 'cancelled_scope': project.scope,
                'evidence': 'DEMO-B5-SOLICITUD-CANCELACION-001',
            },
        )
        base_events = (
            ('evaluacion_tecnica', actors['L3'], 'Evaluación técnica ficticia.',
             'DEMO-B5-EVALUACION-TECNICA-001',
             {'l1_intervention_required': True, 'l1_exception_reason': 'Caso sintético excepcional.'}),
            ('escalamiento_l1', actors['L2'], 'Escalamiento ficticio a L1.',
             'DEMO-B5-ESCALAMIENTO-001',
             {'source': 'evaluacion_comercial_l2', 'within_l2_competence': False,
              'commercial_consequences': 'Consecuencias sintéticas documentadas.',
              'effectivity_conditions': 'Condiciones ficticias registradas.'}),
            ('decision_l1_autorizada', actors['L1'], 'Resolución ficticia L1.',
             'DEMO-B5-RESOLUCION-L1-001',
             {'authority': 'L1 exceptional cancellation',
              'planned_effective_at': (timezone.now() - timedelta(days=2)).isoformat(),
              'preserves_restriction_until_resumption': True}),
        )
        for event_type, actor, reason, evidence, data in base_events:
            self._cancellation_event(cancellation, event_type, actor, reason, evidence, data)
        effective = timezone.now() - timedelta(days=1)
        self._cancellation_event(
            cancellation, 'efectiva', actors['L2'], 'Efectividad ficticia de cancelación.',
            'DEMO-B5-EFECTIVIDAD-CANCELACION-001', {'conditions_satisfied': True}, effective,
        )
        resumption, _ = ProjectResumption.objects.using(DB_ALIAS).get_or_create(
            cancellation=cancellation, defaults={'project': project},
        )
        resumption_events = (
            ('evaluacion_tecnica', actors['L3'], 'Viabilidad técnica sintética.',
             'DEMO-B5-REANUDACION-TECNICA-001', {'feasibility': 'Viable', 'pending_work': 'Tareas históricas conservadas.'}),
            ('decision_comercial_aprobada', actors['L2'], 'Condiciones comerciales sintéticas.',
             'DEMO-B5-REANUDACION-L2-001', {'conditions': 'Condiciones demostrativas.'}),
            ('decision_l1_aprobada', actors['L1'], 'Resolución sintética L1.',
             'DEMO-B5-REANUDACION-L1-001', {'conditions': 'Restricción excepcional levantada.'}),
            ('reanudacion_registrada', actors['L1'], 'Reanudación ficticia registrada.',
             'DEMO-B5-REANUDACION-REGISTRO-001', {}),
        )
        for event_type, actor, reason, evidence, data in resumption_events:
            ProjectResumptionEvent.objects.using(DB_ALIAS).get_or_create(
                resumption=resumption, event_type=event_type,
                defaults={'actor': actor, 'reason': reason, 'evidence': evidence, 'data': data},
            )

    @staticmethod
    def _cancellation_event(cancellation, event_type, actor, reason, evidence, data, effective_at=None):
        ProjectCancellationEvent.objects.using(DB_ALIAS).get_or_create(
            cancellation=cancellation, event_type=event_type,
            defaults={
                'actor': actor, 'reason': reason, 'evidence': evidence,
                'data': data, 'effective_at': effective_at,
            },
        )

    @staticmethod
    def _scenario_counts(projects, service, due):
        return {
            'tasks': Task.objects.using(DB_ALIAS).filter(project__in=projects).count(),
            'payments': CustomerPayment.objects.using(DB_ALIAS).filter(service__client=service.client).count()
                        + CollaboratorPayment.objects.using(DB_ALIAS).filter(reference='DEMO-B5-PAY-001').count(),
            'notices': CommercialPaymentNotice.objects.using(DB_ALIAS).filter(due=due).count(),
            'notifications': InternalNotification.objects.using(DB_ALIAS).filter(task__project__in=projects).count(),
        }

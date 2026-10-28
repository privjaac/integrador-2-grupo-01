import base64
import binascii
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.role_permissions import effective_permissions
from clients.models import (
    Collaborator, InternalNotification, Task, TaskDeadlineNotificationConfig,
)

logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {'Finalizada', 'Cancelada'}
JAVA_PROCESSOR_CLASS = 'elisa.notifications.TaskDeadlineProcessor'


def encode_field(value):
    return base64.urlsafe_b64encode(str(value).encode('utf-8')).decode('ascii').rstrip('=')


def decode_field(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)).decode('utf-8')


def compile_and_run_java(payload):
    source = Path(__file__).resolve().parents[3] / 'java-notifications' / 'src' / 'main' / 'java' / 'elisa' / 'notifications' / 'TaskDeadlineProcessor.java'
    javac = shutil.which('javac')
    java = shutil.which('java')
    if not javac or not java:
        raise CommandError('El procesamiento de vencimientos requiere un JDK local (java y javac).')
    if not source.is_file():
        raise CommandError('No se encuentra el código fuente del procesador Java de notificaciones.')

    with tempfile.TemporaryDirectory(prefix='elisa-notifications-java-') as output_dir:
        try:
            subprocess.run(
                [javac, '-encoding', 'UTF-8', '-d', output_dir, str(source)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                [java, '-cp', output_dir, JAVA_PROCESSOR_CLASS],
                input=payload, check=True, capture_output=True, text=True, timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise CommandError(
                'Falló la compilación o ejecución del procesador Java; consulta el registro operativo.'
            ) from exc
    return result.stdout


def verify_java_runtime():
    """Fail early unless this execution environment has a working JDK."""
    tools = {name: shutil.which(name) for name in ('java', 'javac')}
    if not all(tools.values()):
        raise CommandError('El procesamiento requiere un JDK disponible (java y javac).')
    for name, executable in tools.items():
        try:
            subprocess.run(
                [executable, '-version'], check=True, capture_output=True,
                text=True, timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise CommandError(
                f'No fue posible comprobar la dependencia {name} del JDK.'
            ) from exc


class Command(BaseCommand):
    help = 'Genera avisos internos de recordatorio o vencimiento de tareas usando el procesador Java.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check', action='store_true',
            help='Comprueba el JDK y compila/ejecuta el procesador sin consultar ni modificar datos.',
        )

    def handle(self, *args, **options):
        run_id = uuid.uuid4().hex
        started = time.monotonic()
        self.stdout.write(f'run_id={run_id} status=started')
        try:
            verify_java_runtime()
            if options.get('check'):
                compile_and_run_java('')
                self.stdout.write(
                    f'run_id={run_id} status=ok mode=check duration_ms={self._duration_ms(started)}'
                )
                return
            return self._process(run_id, started)
        except KeyboardInterrupt:
            self.stderr.write(
                f'run_id={run_id} status=interrupted duration_ms={self._duration_ms(started)}'
            )
            raise
        except CommandError:
            self.stderr.write(
                f'run_id={run_id} status=failed error=command_error '
                f'duration_ms={self._duration_ms(started)}'
            )
            raise
        except Exception as exc:
            # Log only the exception type; database/driver messages can contain sensitive values.
            logger.error(
                'Falló el procesamiento de recordatorios run_id=%s error_type=%s',
                run_id, type(exc).__name__,
            )
            self.stderr.write(
                f'run_id={run_id} status=failed error_type={type(exc).__name__} '
                f'duration_ms={self._duration_ms(started)}'
            )
            raise CommandError('No se pudo completar el procesamiento de recordatorios.') from None

    @staticmethod
    def _duration_ms(started):
        return round((time.monotonic() - started) * 1000)

    def _process(self, run_id, started):
        from api.routers.tasks import task_queryset

        now = timezone.now()
        config = TaskDeadlineNotificationConfig.objects.get(key='task_deadline')
        try:
            reminder_cutoff = now + timedelta(days=config.days_before)
        except OverflowError:
            reminder_cutoff = datetime.max.replace(tzinfo=now.tzinfo)
        reminder_window_hours = config.days_before * 24
        candidates = list(Task.objects.filter(
            due_at__isnull=False, due_at__lte=reminder_cutoff,
        ).select_related('responsible__role', 'created_by__role').order_by('id'))
        if not candidates:
            self.stdout.write(
                f'run_id={run_id} status=ok Avisos creados: 0; ya existentes: 0; '
                f'omitidos: 0; duration_ms={self._duration_ms(started)}.'
            )
            return

        candidate_map = {}
        input_lines = []
        for task in candidates:
            allowed = {'responsible': None, 'creator': None}
            for role_name, collaborator in (
                ('responsible', task.responsible), ('creator', task.created_by),
            ):
                if not collaborator.is_active or not collaborator.role or not collaborator.role.is_active:
                    continue
                if 'tasks.view' not in effective_permissions(collaborator.role):
                    continue
                scoped_user = {
                    'role': collaborator.role.level,
                    'collaborator_id': collaborator.pk,
                }
                if task_queryset(scoped_user).filter(pk=task.pk).exists():
                    allowed[role_name] = collaborator.pk
            candidate_map[task.pk] = {'task': task, 'allowed': allowed}
            due_millis = int(task.due_at.timestamp() * 1000)
            now_millis = int(now.timestamp() * 1000)
            input_lines.append('\t'.join((
                str(task.pk), encode_field(task.status), encode_field(task.title),
                str(due_millis), str(now_millis),
                str(allowed['responsible'] or 0), str(allowed['creator'] or 0),
                str(reminder_window_hours),
            )))

        output = compile_and_run_java('\n'.join(input_lines) + '\n')
        created_count = 0
        existing_count = 0
        skipped_count = 0
        for line in output.splitlines():
            fields = line.split('\t')
            if len(fields) == 3 and fields[0] == 'S':
                skipped_count += 1
                logger.info('Se omitió el aviso de la tarea %s: %s', fields[1], fields[2])
                continue
            if len(fields) != 6 or fields[0] != 'N':
                raise CommandError('El procesador Java devolvió un registro inválido.')
            try:
                task_id = int(fields[1])
                kind = fields[2]
                recipient_id = int(fields[3])
                title = decode_field(fields[4])
                message = decode_field(fields[5])
            except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
                raise CommandError('El procesador Java devolvió datos de notificación inválidos.') from exc
            candidate = candidate_map.get(task_id)
            if candidate is None or kind not in {'tarea_recordatorio', 'tarea_vencida'}:
                raise CommandError('El procesador Java devolvió una tarea o tipo no solicitado.')
            allowed_ids = {
                candidate['allowed']['responsible'],
                candidate['allowed']['creator'] if kind == 'tarea_vencida' else None,
            }
            if recipient_id not in allowed_ids or len(title) > 100 or len(message) > 300:
                raise CommandError('El procesador Java devolvió un destinatario o contenido fuera de alcance.')

            snapshot = candidate['task']
            with transaction.atomic():
                task = Task.objects.select_for_update(of=('self',)).select_related(
                    'responsible__role', 'created_by__role',
                ).filter(pk=task_id).first()
                if (
                    task is None or task.due_at != snapshot.due_at
                    or task.status in TERMINAL_STATUSES
                    or (kind == 'tarea_recordatorio' and task.responsible_id != recipient_id)
                    or (kind == 'tarea_vencida' and recipient_id not in {task.responsible_id, task.created_by_id})
                    or (kind == 'tarea_recordatorio' and not (now < task.due_at <= reminder_cutoff))
                    or (kind == 'tarea_vencida' and task.due_at > now)
                ):
                    skipped_count += 1
                    continue

                recipient = Collaborator.objects.select_related('role').filter(
                    pk=recipient_id, is_active=True, role__is_active=True,
                ).first()
                if recipient is None:
                    skipped_count += 1
                    continue
                if 'tasks.view' not in effective_permissions(recipient.role):
                    skipped_count += 1
                    continue
                scoped_user = {'role': recipient.role.level, 'collaborator_id': recipient.pk}
                if not task_queryset(scoped_user).filter(pk=task.pk).exists():
                    skipped_count += 1
                    continue

                source_key = f'task:{task.pk}:{kind}:{task.due_at.isoformat()}:recipient:{recipient_id}'
                _notice, created = InternalNotification.objects.get_or_create(
                    source_key=source_key,
                    defaults={
                        'task': task, 'recipient': recipient, 'notice_type': kind,
                        'title': title, 'message': message,
                    },
                )
                if created:
                    created_count += 1
                else:
                    existing_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'run_id={run_id} status=ok Avisos creados: {created_count}; '
            f'ya existentes: {existing_count}; omitidos: {skipped_count}; '
            f'duration_ms={self._duration_ms(started)}.'
        ))

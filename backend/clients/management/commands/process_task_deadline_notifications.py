import base64
import binascii
import logging
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.role_permissions import effective_permissions
from clients.models import Collaborator, InternalNotification, Task

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
            detail = getattr(exc, 'stderr', '') or str(exc)
            raise CommandError(f'Falló la compilación o ejecución del procesador Java: {detail[:1200]}') from exc
    return result.stdout


class Command(BaseCommand):
    help = 'Genera avisos internos de recordatorio o vencimiento de tareas usando el procesador Java.'

    def handle(self, *args, **options):
        from api.routers.tasks import task_queryset

        now = timezone.now()
        candidates = list(Task.objects.filter(
            due_at__isnull=False, due_at__lte=now + timedelta(hours=24),
        ).select_related('responsible__role', 'created_by__role').order_by('id'))
        if not candidates:
            self.stdout.write('Sin tareas con vencimiento dentro de las próximas 24 horas o ya vencidas.')
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
                task = Task.objects.select_for_update().select_related(
                    'responsible__role', 'created_by__role',
                ).filter(pk=task_id).first()
                if (
                    task is None or task.due_at != snapshot.due_at
                    or task.status in TERMINAL_STATUSES
                    or (kind == 'tarea_recordatorio' and task.responsible_id != recipient_id)
                    or (kind == 'tarea_vencida' and recipient_id not in {task.responsible_id, task.created_by_id})
                    or (kind == 'tarea_recordatorio' and not (now < task.due_at <= now + timedelta(hours=24)))
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
            f'Avisos creados: {created_count}; ya existentes: {existing_count}; omitidos: {skipped_count}.'
        ))

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from api.role_permissions import effective_permissions
from clients.models import Collaborator, InternalNotification, TaskEvent

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TaskEvent)
def notify_task_event_recipients(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(
            lambda event_id=instance.pk: _create_task_event_notifications(event_id),
            robust=True,
        )


def _create_task_event_notifications(event_id):
    try:
        _persist_task_event_notifications(event_id)
    except Exception:
        logger.exception('No se pudieron generar avisos internos para el evento de tarea %s', event_id)


def _persist_task_event_notifications(event_id):
    event = TaskEvent.objects.select_related('task').get(pk=event_id)
    task = event.task
    recipients = set()
    is_assignment = event.event_type in {'asignada', 'creada'} and event.assignee_id
    is_reassignment = event.event_type == 'ejecutor_reasignado'
    status_changed = bool(
        event.previous_status and event.new_status
        and event.previous_status != event.new_status
    )
    if is_assignment:
        recipients.add(event.assignee_id)
    if is_reassignment:
        if event.assignee_id:
            recipients.add(event.assignee_id)
        if event.previous_assignee_id:
            recipients.add(event.previous_assignee_id)
    if status_changed:
        recipients.update((task.created_by_id, task.responsible_id))
        if task.assignee_id:
            recipients.add(task.assignee_id)
    recipients.discard(event.actor_id)
    if not recipients:
        return

    active_people = Collaborator.objects.filter(
        pk__in=recipients, is_active=True, role__is_active=True,
    ).select_related('role')
    active_ids = {
        person.pk for person in active_people
        if 'tasks.view' in effective_permissions(person.role)
    }
    InternalNotification.objects.bulk_create([
        InternalNotification(
            event=event,
            task=task,
            recipient_id=recipient_id,
            notice_type='event',
            source_key=f'event:{event.pk}:recipient:{recipient_id}',
            title=(
                'Nueva tarea asignada' if is_assignment and recipient_id == event.assignee_id
                else 'Te removieron de la tarea' if is_reassignment
                and recipient_id == event.previous_assignee_id
                else 'Tarea reasignada' if is_reassignment and recipient_id == event.assignee_id
                else 'Estado de tarea actualizado'
            ),
            message=(
                f'Se te ha asignado una nueva tarea: {task.title}'
                if is_assignment and recipient_id == event.assignee_id
                else f'Se te ha removido de la tarea {task.title}.'
                if is_reassignment and recipient_id == event.previous_assignee_id
                else f'Se te ha reasignado la tarea {task.title}.'
                if is_reassignment and recipient_id == event.assignee_id
                else f'La tarea {task.title} cambió al estado {event.new_status}.'
            ),
        )
        for recipient_id in active_ids
    ], ignore_conflicts=True)

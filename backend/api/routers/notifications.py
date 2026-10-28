from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from fastapi import Depends, HTTPException
from pydantic import Field

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.safe_input import SafeInputModel
from api.routers.tasks import task_queryset
from clients.models import (
    Client, Collaborator, InternalNotification, TaskDeadlineNotificationConfig,
    TaskDeadlineNotificationConfigEvent,
)

router = APIRouter()


class TaskDeadlineSettingsInput(SafeInputModel):
    days_before: int = Field(ge=1, le=2147483647)


def task_deadline_config_response(config):
    return {
        'days_before': config.days_before,
        'updated_by_id': config.updated_by_id,
        'updated_at': config.updated_at,
        'history': [{
            'previous_days_before': event.previous_days_before,
            'new_days_before': event.new_days_before,
            'actor_id': event.actor_id,
            'actor_name': f'{event.actor.first_name} {event.actor.last_name}'.strip(),
            'occurred_at': event.occurred_at,
        } for event in config.history.select_related('actor')[:50]],
    }


def require_own_commercial_inbox_scope(user: dict) -> None:
    if 'tasks.view' in user.get('permissions', []):
        return
    if not Client.objects.filter(commercial_responsible_id=user['collaborator_id']).exists():
        raise HTTPException(status_code=403, detail='El rol no tiene un ámbito propio de notificaciones')


@router.get('/task-deadline-settings')
def get_task_deadline_settings(user: dict = Depends(get_current_user)):
    try:
        config = TaskDeadlineNotificationConfig.objects.get(key='task_deadline')
    except TaskDeadlineNotificationConfig.DoesNotExist as exc:
        raise HTTPException(status_code=503, detail='La configuración de recordatorios no está inicializada') from exc
    return task_deadline_config_response(config)


@router.put('/task-deadline-settings')
def update_task_deadline_settings(
    payload: TaskDeadlineSettingsInput, user: dict = Depends(get_current_user),
):
    actor = Collaborator.objects.select_related('role').filter(
        pk=user['collaborator_id'], is_active=True, role__is_active=True,
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador no está activo')
    try:
        with transaction.atomic():
            config = TaskDeadlineNotificationConfig.objects.select_for_update().get(key='task_deadline')
            previous_days_before = config.days_before
            if previous_days_before != payload.days_before:
                config.days_before = payload.days_before
                config.updated_by = actor
                config.save(update_fields=['days_before', 'updated_by', 'updated_at'])
                TaskDeadlineNotificationConfigEvent.objects.create(
                    config=config, actor=actor,
                    previous_days_before=previous_days_before, new_days_before=config.days_before,
                )
    except TaskDeadlineNotificationConfig.DoesNotExist as exc:
        raise HTTPException(status_code=503, detail='La configuración de recordatorios no está inicializada') from exc
    return task_deadline_config_response(config)


@router.get('/')
def list_internal_notifications(user: dict = Depends(get_current_user)):
    require_own_commercial_inbox_scope(user)
    own_notifications = InternalNotification.objects.filter(recipient_id=user['collaborator_id'])
    allowed_scope = Q(
        commercial_due__client__commercial_responsible_id=user['collaborator_id'],
        recipient__is_active=True, recipient__role__is_active=True,
    )
    if 'tasks.view' in user.get('permissions', []):
        readable_task_ids = task_queryset(user).values_list('pk', flat=True)
        allowed_scope |= (
            Q(task_id__in=readable_task_ids)
            | Q(event__task_id__in=readable_task_ids)
            | Q(event__event_type='ejecutor_reasignado', event__previous_assignee_id=user['collaborator_id'])
        )
    own_notifications = own_notifications.filter(allowed_scope)
    rows = list(
        own_notifications.select_related('event')[:50]
    )
    unread = own_notifications.filter(read_at__isnull=True).count()
    return {
        'unread_count': unread,
        'items': [{
            'id': item.id,
            'task_id': item.task_id or (item.event.task_id if item.event_id else None),
            'event_type': item.event.event_type if item.event_id else item.notice_type,
            'title': item.title,
            'message': item.message,
            'created_at': item.created_at,
            'read_at': item.read_at,
        } for item in rows],
    }


@router.patch('/{notification_id}/read')
def mark_internal_notification_read(
    notification_id: int, user: dict = Depends(get_current_user),
):
    require_own_commercial_inbox_scope(user)
    allowed = InternalNotification.objects.filter(recipient_id=user['collaborator_id'])
    allowed_scope = Q(
        commercial_due__client__commercial_responsible_id=user['collaborator_id'],
        recipient__is_active=True, recipient__role__is_active=True,
    )
    if 'tasks.view' in user.get('permissions', []):
        readable_task_ids = task_queryset(user).values_list('pk', flat=True)
        allowed_scope |= (
            Q(task_id__in=readable_task_ids)
            | Q(event__task_id__in=readable_task_ids)
            | Q(event__event_type='ejecutor_reasignado', event__previous_assignee_id=user['collaborator_id'])
        )
    allowed = allowed.filter(allowed_scope)
    updated = allowed.filter(
        pk=notification_id, read_at__isnull=True,
    ).update(read_at=timezone.now())
    if not updated and not allowed.filter(pk=notification_id).exists():
        raise HTTPException(404, 'Notificación no encontrada')
    return {'id': notification_id, 'read': True}

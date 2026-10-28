from django.utils import timezone
from django.db.models import Q
from fastapi import Depends, HTTPException

from api.dependencies import get_current_user
from api.router import APIRouter
from api.routers.tasks import task_queryset
from clients.models import InternalNotification

router = APIRouter()


@router.get('/')
def list_internal_notifications(user: dict = Depends(get_current_user)):
    own_notifications = InternalNotification.objects.filter(recipient_id=user['collaborator_id'])
    if 'tasks.view' not in user.get('permissions', []):
        own_notifications = own_notifications.none()
    else:
        readable_task_ids = task_queryset(user).values_list('pk', flat=True)
        own_notifications = own_notifications.filter(
            Q(event__task_id__in=readable_task_ids)
            | Q(event__event_type='ejecutor_reasignado', event__previous_assignee_id=user['collaborator_id'])
        )
    rows = list(
        own_notifications.select_related('event')[:50]
    )
    unread = own_notifications.filter(read_at__isnull=True).count()
    return {
        'unread_count': unread,
        'items': [{
            'id': item.id,
            'task_id': item.event.task_id,
            'event_type': item.event.event_type,
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
    allowed = InternalNotification.objects.filter(recipient_id=user['collaborator_id'])
    if 'tasks.view' in user.get('permissions', []):
        readable_task_ids = task_queryset(user).values_list('pk', flat=True)
        allowed = allowed.filter(
            Q(event__task_id__in=readable_task_ids)
            | Q(event__event_type='ejecutor_reasignado', event__previous_assignee_id=user['collaborator_id'])
        )
    else:
        allowed = allowed.none()
    updated = allowed.filter(
        pk=notification_id, read_at__isnull=True,
    ).update(read_at=timezone.now())
    if not updated and not allowed.filter(pk=notification_id).exists():
        raise HTTPException(404, 'Notificación no encontrada')
    return {'id': notification_id, 'read': True}

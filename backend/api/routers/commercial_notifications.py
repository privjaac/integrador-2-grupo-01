from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from fastapi import Depends, HTTPException, Query

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.commercial_notifications import CommercialNoticeConfigUpdate
from clients.models import (
    Client,
    Collaborator,
    CommercialPaymentNotice,
    CommercialPaymentNoticeConfig,
    CommercialPaymentNoticeConfigEvent,
    DocumentedPaymentDue,
    InternalNotification,
)


router = APIRouter()
VIEW_ROLES = ('L1', 'L2', 'L3')
ADMIN_ROLES = ('L1', 'L2')
NOTICE_CHANNELS = ('whatsapp', 'email', 'internal')


def active_notice_viewer(user: dict) -> Collaborator:
    role = user.get('role')
    if role not in VIEW_ROLES:
        raise HTTPException(status_code=403, detail='No tienes acceso al panel de alertas')
    actor = Collaborator.objects.select_related('role').filter(
        pk=user.get('collaborator_id'), is_active=True, role__is_active=True, role__level=role,
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador no está activo')
    return actor


def active_notice_admin(user: dict) -> Collaborator:
    role = user.get('role')
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail='La operación corresponde a SA o SM')
    actor = Collaborator.objects.select_related('role').filter(
        pk=user.get('collaborator_id'), is_active=True, role__is_active=True, role__level=role,
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador no tiene autoridad vigente')
    return actor


def _config_row(config: CommercialPaymentNoticeConfig, *, include_history: bool = False) -> dict:
    row = {
        'channel': config.channel,
        'anticipation_days': config.anticipation_days,
        'is_active': config.is_active,
        'updated_by_id': config.updated_by_id,
        'updated_by_name': (
            f'{config.updated_by.first_name} {config.updated_by.last_name}'.strip()
            if config.updated_by_id else None
        ),
        'updated_at': config.updated_at,
    }
    if include_history:
        row['history'] = [{
            'previous_days': event.previous_days,
            'new_days': event.new_days,
            'previous_active': event.previous_active,
            'new_active': event.new_active,
            'actor_id': event.actor_id,
            'actor_name': f'{event.actor.first_name} {event.actor.last_name}'.strip(),
            'occurred_at': event.occurred_at,
        } for event in config.history.select_related('actor')[:50]]
    return row


@router.get('/commercial-notice-config')
def get_commercial_notice_config(user: dict = Depends(get_current_user)):
    active_notice_admin(user)
    configs = CommercialPaymentNoticeConfig.objects.select_related('updated_by').order_by('channel')
    return [_config_row(config, include_history=True) for config in configs]


@router.put('/commercial-notice-config/{channel}')
def update_commercial_notice_config(
    channel: str,
    payload: CommercialNoticeConfigUpdate,
    user: dict = Depends(get_current_user),
):
    actor = active_notice_admin(user)
    if channel not in NOTICE_CHANNELS:
        raise HTTPException(status_code=404, detail='Canal de notificación no encontrado')
    try:
        with transaction.atomic():
            config = CommercialPaymentNoticeConfig.objects.select_for_update().get(channel=channel)
            before_days = list(config.anticipation_days)
            before_active = config.is_active
            if before_days != payload.anticipation_days or before_active != payload.is_active:
                config.anticipation_days = payload.anticipation_days
                config.is_active = payload.is_active
                config.updated_by = actor
                config.save(update_fields=['anticipation_days', 'is_active', 'updated_by', 'updated_at'])
                CommercialPaymentNoticeConfigEvent.objects.create(
                    config=config, actor=actor,
                    previous_days=before_days, new_days=list(config.anticipation_days),
                    previous_active=before_active, new_active=config.is_active,
                )
    except CommercialPaymentNoticeConfig.DoesNotExist as exc:
        raise HTTPException(status_code=503, detail='La configuración comercial no está inicializada') from exc
    config = CommercialPaymentNoticeConfig.objects.select_related('updated_by').get(pk=config.pk)
    return _config_row(config, include_history=True)


def _notice_row(notice: CommercialPaymentNotice, *, disclose_contact: bool) -> dict:
    due = notice.due
    client = due.client
    if notice.channel == 'internal':
        recipient = (
            f'{notice.recipient.first_name} {notice.recipient.last_name}'.strip()
            if disclose_contact and notice.recipient_id else 'Responsable comercial'
        )
    else:
        recipient = notice.destination_snapshot if disclose_contact else 'Cliente'
    return {
        'id': notice.id,
        'source_notice_id': notice.resend_of_id,
        'attempt_number': notice.attempt_number,
        'channel': notice.channel,
        'alert_type': f'payment_reminder_{notice.channel}',
        'recipient': recipient,
        'status': notice.status,
        'due_id': due.id,
        'client_id': client.id,
        'client_name': client.name,
        'service_name': due.service.service_name,
        'due_date': due.due_date,
        'anticipation_days': notice.anticipation_days,
        'created_at': notice.created_at,
        'available_at': notice.available_at,
        'error_message': notice.error_message if disclose_contact else ('No se pudo preparar el aviso.' if notice.status == 'fallida' else ''),
    }


@router.get('/upcoming')
def list_upcoming_commercial_notices(
    search: str | None = Query(default=None, max_length=200),
    channel: str | None = Query(default=None, pattern='^(whatsapp|email|internal)$'),
    status: str | None = Query(default=None, pattern='^(preparada|disponible|fallida)$'),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    active_notice_viewer(user)
    today = timezone.localdate()
    end_date = today + timedelta(days=30)
    due_query = DocumentedPaymentDue.objects.filter(
        client__status='activo', due_date__gte=today, due_date__lte=end_date,
    ).select_related('client', 'service')
    if search:
        due_query = due_query.filter(
            Q(client__name__icontains=search.strip()) | Q(service__service_name__icontains=search.strip())
        )
    due_items = list(due_query.order_by('due_date', 'client__name', 'id'))
    due_ids = [item.id for item in due_items]
    configs = list(CommercialPaymentNoticeConfig.objects.filter(is_active=True).order_by('channel'))
    notices = CommercialPaymentNotice.objects.filter(due_id__in=due_ids).select_related(
        'due__client', 'due__service', 'recipient',
    ).order_by('due_id', 'channel', '-created_at', '-id')
    latest_by_due_channel: dict[tuple[int, str], CommercialPaymentNotice] = {}
    for notice in notices:
        latest_by_due_channel.setdefault((notice.due_id, notice.channel), notice)

    results = []
    disclose_contact = user.get('role') in ADMIN_ROLES
    for due in due_items:
        channels = {
            item.channel for item in configs if (due.due_date - today).days in item.anticipation_days
        } | {
            current_channel for due_id, current_channel in latest_by_due_channel if due_id == due.id
        }
        if channel:
            channels &= {channel}
        if not channels:
            if not channel and not status:
                results.append({
                    'id': None, 'source_notice_id': None, 'attempt_number': 0,
                    'channel': None, 'alert_type': None, 'recipient': None,
                    'status': None, 'due_id': due.id, 'client_id': due.client_id,
                    'client_name': due.client.name, 'service_name': due.service.service_name,
                    'due_date': due.due_date, 'anticipation_days': [],
                    'created_at': None, 'available_at': None, 'error_message': '',
                    'days_remaining': (due.due_date - today).days,
                })
            continue
        for current_channel in sorted(channels):
            notice = latest_by_due_channel.get((due.id, current_channel))
            if notice:
                if status and notice.status != status:
                    continue
                row = _notice_row(notice, disclose_contact=disclose_contact)
                row['anticipation_days'] = notice.anticipation_days
            else:
                if status:
                    continue
                config = next((item for item in configs if item.channel == current_channel), None)
                row = {
                    'id': None, 'source_notice_id': None, 'attempt_number': 0,
                    'channel': current_channel, 'alert_type': f'payment_reminder_{current_channel}',
                    'recipient': None,
                    'status': None, 'due_id': due.id, 'client_id': due.client_id,
                    'client_name': due.client.name, 'service_name': due.service.service_name,
                    'due_date': due.due_date,
                    'anticipation_days': config.anticipation_days if config else [],
                    'created_at': None, 'available_at': None, 'error_message': '',
                }
            row['days_remaining'] = (due.due_date - today).days
            results.append(row)
    results.sort(key=lambda row: (row['due_date'], row['client_name'], row['channel'] or ''))
    return {'count': len(results), 'items': results[offset:offset + limit]}


@router.get('/logs')
def list_commercial_notice_logs(
    search: str | None = Query(default=None, max_length=200),
    channel: str | None = Query(default=None, pattern='^(whatsapp|email|internal)$'),
    status: str | None = Query(default=None, pattern='^(preparada|disponible|fallida)$'),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    active_notice_viewer(user)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail='El rango de fechas no es válido')
    rows = CommercialPaymentNotice.objects.select_related(
        'due__client', 'due__service', 'recipient',
    )
    if channel:
        rows = rows.filter(channel=channel)
    if status:
        rows = rows.filter(status=status)
    if date_from:
        rows = rows.filter(created_at__date__gte=date_from)
    if date_to:
        rows = rows.filter(created_at__date__lte=date_to)
    if search:
        term = search.strip()
        query = Q(due__client__name__icontains=term) | Q(due__service__service_name__icontains=term)
        if user.get('role') in ADMIN_ROLES:
            query |= Q(destination_snapshot__icontains=term) | Q(recipient__first_name__icontains=term) | Q(recipient__last_name__icontains=term)
        rows = rows.filter(query)
    count = rows.count()
    items = [_notice_row(item, disclose_contact=user.get('role') in ADMIN_ROLES) for item in rows.order_by('-created_at', '-id')[offset:offset + limit]]
    return {'count': count, 'limit': limit, 'offset': offset, 'items': items}


@router.get('/logs/{notice_id}')
def get_commercial_notice_detail(notice_id: int, user: dict = Depends(get_current_user)):
    active_notice_viewer(user)
    notice = CommercialPaymentNotice.objects.select_related(
        'due__client', 'due__service', 'due__recorded_by', 'recipient', 'resent_by', 'resend_of',
    ).filter(pk=notice_id).first()
    if notice is None:
        raise HTTPException(status_code=404, detail='Aviso no encontrado')
    result = _notice_row(notice, disclose_contact=user.get('role') in ADMIN_ROLES)
    result.update({
        'title': notice.title,
        'message': notice.message,
        'obligation_reference': notice.due.obligation_reference if user.get('role') in ADMIN_ROLES else None,
        'evidence_reference': notice.due.evidence_reference if user.get('role') in ADMIN_ROLES else None,
        'recorded_by_id': notice.due.recorded_by_id if user.get('role') in ADMIN_ROLES else None,
        'resent_by_id': notice.resent_by_id,
        'resent_at': notice.created_at if notice.resend_of_id else None,
        'source_notice_id': notice.resend_of_id,
    })
    return result


@router.post('/logs/{notice_id}/resend', status_code=201)
def resend_internal_commercial_notice(notice_id: int, user: dict = Depends(get_current_user)):
    actor = active_notice_admin(user)
    with transaction.atomic():
        original = CommercialPaymentNotice.objects.select_for_update(of=('self',)).filter(
            pk=notice_id, resend_of__isnull=True,
        ).select_related('due').first()
        if original is None:
            raise HTTPException(status_code=404, detail='Aviso original no encontrado')
        if original.channel != 'internal' or original.status != 'fallida':
            raise HTTPException(
                status_code=409,
                detail='Solo se puede reintentar un aviso interno fallido; los canales externos no están conectados.',
            )
        previous_attempt = CommercialPaymentNotice.objects.filter(
            resend_of=original,
        ).order_by('-attempt_number').first()
        if previous_attempt and previous_attempt.status == 'disponible':
            raise HTTPException(status_code=409, detail='El aviso interno ya está disponible para su destinatario')

        due = DocumentedPaymentDue.objects.select_for_update().select_related('service').get(pk=original.due_id)
        client = Client.objects.select_for_update().get(pk=due.client_id)
        if client.status != 'activo':
            raise HTTPException(status_code=409, detail='El cliente no está activo para un nuevo aviso comercial')
        recipient = Collaborator.objects.select_for_update(of=('self',)).select_related('role').filter(
            pk=client.commercial_responsible_id, is_active=True, role__is_active=True,
        ).first()
        if recipient is None:
            raise HTTPException(status_code=409, detail='No hay responsable comercial vigente y activo')
        attempt_number = previous_attempt.attempt_number + 1 if previous_attempt else 1
        now = timezone.now()
        source_key = f'commercial-due:{due.pk}:internal:{original.anticipation_days}:resend:{original.pk}:{attempt_number}'
        attempt = CommercialPaymentNotice.objects.create(
            due=due, channel='internal', anticipation_days=original.anticipation_days,
            recipient=recipient, source_key=source_key, status='disponible',
            title='Seguimiento comercial próximo',
            message='Tienes un seguimiento comercial que requiere atención en una fecha próxima.',
            available_at=now, resend_of=original, resent_by=actor, attempt_number=attempt_number,
        )
        InternalNotification.objects.create(
            recipient=recipient, commercial_due=due,
            notice_type='commercial_payment_reminder', source_key=source_key,
            title=attempt.title, message=attempt.message,
        )
    return {
        'id': attempt.id, 'status': attempt.status,
        'available_at': attempt.available_at, 'source_notice_id': original.id,
        'resent_by_id': actor.id, 'attempt_number': attempt.attempt_number,
        'delivery': 'available_in_internal_inbox',
    }

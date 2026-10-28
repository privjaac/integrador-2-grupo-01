from datetime import date
from decimal import Decimal
import logging
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Sum
from fastapi import Depends, Header, HTTPException, Query, Response, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.role_permissions import effective_permissions
from api.schemas.collaborator_payments import CollaboratorPaymentWrite
from clients.models import Collaborator, CollaboratorPayment


router = APIRouter()
logger = logging.getLogger(__name__)


def payment_actor(user: dict, action: str) -> Collaborator:
    level = user.get('role')
    required = f'collaboratorPayments.{action}'
    if required not in user.get('permissions', []):
        logger.warning('collaborator_payment_access_denied action=%s actor_id=%s', action, user.get('collaborator_id'))
        raise HTTPException(status_code=403, detail='El rol organizacional no tiene este permiso')
    if level not in {'L1', 'L2'}:
        logger.warning('collaborator_payment_access_denied action=%s actor_id=%s level=%s', action, user.get('collaborator_id'), level)
        raise HTTPException(status_code=403, detail='Solo SA y SM pueden consultar o registrar pagos')
    actor = Collaborator.objects.select_related('role').filter(
        pk=user.get('collaborator_id'), is_active=True, role__is_active=True, role__level=level,
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador no está activo')
    return actor


def payment_json(item: CollaboratorPayment) -> dict:
    return {
        'id': item.id,
        'reference': item.reference,
        'collaborator_id': item.collaborator_id,
        'collaborator_name': f'{item.collaborator.first_name} {item.collaborator.last_name}'.strip(),
        'collaborator_cupe': item.collaborator.cupe,
        'payment_date': item.payment_date,
        'amount': format(item.amount, '.2f'),
        'currency': 'PEN',
        'concept': item.concept,
        'observation': item.observation,
        'registered_by_id': item.registered_by_id,
        'registered_by_name': f'{item.registered_by.first_name} {item.registered_by.last_name}'.strip(),
        'registered_at': item.registered_at,
    }


def matches_idempotent_request(item, payload, actor):
    return (
        item.collaborator_id == payload.collaborator_id
        and item.registered_by_id == actor.id
        and item.payment_date == payload.payment_date
        and item.amount == payload.amount
        and item.concept == payload.concept
        and item.observation == payload.observation
    )


@router.get('/')
def list_collaborator_payments(
    collaborator_id: int | None = Query(default=None, gt=0),
    payment_date: date | None = None,
    concept: str | None = Query(default=None, max_length=150),
    user: dict = Depends(get_current_user),
):
    payment_actor(user, 'view')
    rows = CollaboratorPayment.objects.select_related('collaborator', 'registered_by')
    if collaborator_id is not None:
        rows = rows.filter(collaborator_id=collaborator_id)
    if payment_date is not None:
        rows = rows.filter(payment_date=payment_date)
    if concept:
        rows = rows.filter(concept__icontains=concept.strip())
    rows = rows.order_by('-payment_date', '-registered_at', '-id')
    summary = rows.aggregate(total=Sum('amount'))
    latest = rows.first()
    return {
        'items': [payment_json(item) for item in rows],
        'summary': {
            'total_paid': format(summary['total'] or Decimal('0.00'), '.2f'),
            'last_payment_date': latest.payment_date if latest else None,
            'count': rows.count(),
            'currency': 'PEN',
        },
    }


@router.get('/collaborators')
def get_payment_collaborators(user: dict = Depends(get_current_user)):
    payment_actor(user, 'view')
    return list(Collaborator.objects.filter(
        is_active=True, role__is_active=True,
    ).order_by('last_name', 'first_name').values(
        'id', 'first_name', 'last_name', 'email', 'cupe',
    ))


@router.post('/', status_code=status.HTTP_201_CREATED)
def record_collaborator_payment(
    payload: CollaboratorPaymentWrite,
    response: Response,
    idempotency_key: UUID = Header(alias='Idempotency-Key'),
    user: dict = Depends(get_current_user),
):
    actor = payment_actor(user, 'record')
    try:
        with transaction.atomic():
            existing = CollaboratorPayment.objects.select_for_update().select_related(
                'collaborator', 'registered_by',
            ).filter(request_key=idempotency_key).first()
            if existing is not None:
                if not matches_idempotent_request(existing, payload, actor):
                    raise HTTPException(status_code=409, detail='La clave de solicitud ya se utilizó para otro pago')
                response.status_code = status.HTTP_200_OK
                return payment_json(existing)
            target = Collaborator.objects.select_for_update().filter(
                pk=payload.collaborator_id, is_active=True,
            ).first()
            if target is None:
                logger.warning('collaborator_payment_target_not_found actor_id=%s target_id=%s', actor.id, payload.collaborator_id)
                raise HTTPException(status_code=404, detail='Colaborador no encontrado')
            locked_actor = Collaborator.objects.select_for_update().select_related('role').filter(
                pk=actor.pk, is_active=True, role__is_active=True, role__level=user.get('role'),
            ).first()
            if locked_actor is None:
                raise HTTPException(status_code=403, detail='El colaborador no está activo')
            if 'collaboratorPayments.record' not in effective_permissions(locked_actor.role):
                raise HTTPException(status_code=403, detail='El rol organizacional no tiene este permiso')
            item = CollaboratorPayment.objects.create(
                collaborator=target,
                payment_date=payload.payment_date,
                amount=payload.amount,
                concept=payload.concept,
                observation=payload.observation,
                request_key=idempotency_key,
                registered_by=locked_actor,
            )
            item.reference = f'ELP-{item.pk:08d}'
            item.save(update_fields=['reference'])
            item = CollaboratorPayment.objects.select_related('collaborator', 'registered_by').get(pk=item.pk)
    except IntegrityError as exc:
        existing = CollaboratorPayment.objects.select_related('collaborator', 'registered_by').filter(
            request_key=idempotency_key,
        ).first()
        if existing is not None and matches_idempotent_request(existing, payload, actor):
            response.status_code = status.HTTP_200_OK
            return payment_json(existing)
        raise HTTPException(status_code=409, detail='No se pudo asignar una referencia única al pago') from exc
    logger.info(
        'collaborator_payment_recorded actor_id=%s collaborator_id=%s payment_id=%s reference=%s amount=%s payment_date=%s',
        actor.id, item.collaborator_id, item.id, item.reference, item.amount, item.payment_date,
    )
    return payment_json(item)

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from fastapi import Depends, HTTPException
from django.db.models import Count, Q
from django.utils import timezone

from api.dependencies import get_current_user
from api.router import APIRouter
from api.routers.clients import service_next_due_date
from clients.models import (
    Client, Collaborator, ContractedService, CustomerPayment,
)

router = APIRouter()
DASHBOARD_ROLES = ('L1', 'L2', 'L3')
FINANCIAL_ROLES = ('L1', 'L2')
MONTH_LABELS = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')


def _first_day_month(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _summary_client(client: Client) -> dict:
    return {
        'id': client.id, 'cupe': client.cupe, 'name': client.name,
        'plan': client.plan, 'status': client.status,
        'registration_date': client.registration_date,
        'web_type_name': client.web_type.name if client.web_type_id else None,
    }


def _month_series(as_of: date) -> list[date]:
    current = _first_day_month(as_of)
    return [_shift_month(current, offset) for offset in range(-11, 1)]


def _monthly_revenue(as_of: date) -> list[dict]:
    months = _month_series(as_of)
    start, end = months[0], as_of
    # Preserve zero-valued series for documented contract currencies too,
    # without inventing a currency when there are no confirmed receipts.
    amounts: dict[str, dict[date, Decimal]] = {
        currency: {}
        for currency in ContractedService.objects.exclude(currency='').values_list('currency', flat=True).distinct()
    }
    receipts = CustomerPayment.objects.filter(
        confirmed_at__isnull=False, effective_date__gte=start, effective_date__lte=end,
    ).prefetch_related('adjustments')
    for payment in receipts:
        month = _first_day_month(payment.effective_date)
        per_month = amounts.setdefault(payment.currency, {})
        per_month[month] = per_month.get(month, Decimal('0')) + payment.amount
        for adjustment in payment.adjustments.all():
            if adjustment.confirmed_at is not None:
                per_month[month] += adjustment.amount
    return [
        {
            'currency': currency,
            'months': [
                {
                    'period': month.strftime('%Y-%m'),
                    'label': f'{MONTH_LABELS[month.month - 1]} {str(month.year)[-2:]}',
                    'amount': str(per_month.get(month, Decimal('0.00'))),
                }
                for month in months
            ],
        }
        for currency, per_month in sorted(amounts.items())
    ]


def _service_row(service: ContractedService, recurrence_date: date | None = None) -> dict:
    client = service.client
    return {
        'service_id': service.id, 'client_id': client.id, 'name': client.name,
        'cupe': client.cupe, 'plan': client.plan, 'status': client.status,
        'service_name': service.service_name,
        'web_type_name': service.catalog_service.name if service.catalog_service_id else None,
        'features': sorted(feature.feature.name for feature in client.features.all()),
        'effective_start': service.effective_start,
        'documented_expiration': service.documented_expiration,
        'next_recurrence_date': recurrence_date,
    }


def build_dashboard_summary(user: dict, as_of: date | None = None) -> dict:
    role = user.get('role')
    if role not in DASHBOARD_ROLES:
        raise HTTPException(status_code=403, detail='No tienes acceso al dashboard')
    if not Collaborator.objects.filter(
        pk=user.get('collaborator_id'), is_active=True, role__level=role,
    ).exists():
        raise HTTPException(status_code=403, detail='El colaborador no está activo')

    as_of = as_of or timezone.localdate()
    clients = list(Client.objects.select_related('web_type').prefetch_related('features__feature'))
    collaborator_counts = Collaborator.objects.aggregate(
        total=Count('id'), active=Count('id', filter=Q(is_active=True)),
    )
    services = ContractedService.objects.select_related(
        'client', 'catalog_service',
    ).prefetch_related('client__features__feature')

    active_services = []
    upcoming_expirations = []
    upcoming_recurrences = []
    expired = []
    for service in services:
        client = service.client
        expiration = service.documented_expiration
        if service.effective_start and service.effective_start <= as_of:
            if client.status == 'activo' and (expiration is None or expiration >= as_of):
                active_services.append(_service_row(service))
        if expiration:
            if expiration < as_of:
                expired.append(_service_row(service))
            elif as_of <= expiration <= as_of + timedelta(days=30):
                upcoming_expirations.append(_service_row(service))
        if service.effective_start and service.effective_start <= as_of and service.frequency != 'unica':
            due = service_next_due_date(service, as_of)
            if due and as_of <= due <= as_of + timedelta(days=30):
                upcoming_recurrences.append(_service_row(service, due))

    result = {
        'as_of': as_of,
        'clients': [_summary_client(client) for client in clients],
        'collaborators': {
            'total': collaborator_counts['total'] or 0,
            'active': collaborator_counts['active'] or 0,
            'inactive': (collaborator_counts['total'] or 0) - (collaborator_counts['active'] or 0),
        },
        'services': {
            'active': active_services,
            'upcoming_expirations_30_days': upcoming_expirations,
            'upcoming_recurrences_30_days': upcoming_recurrences,
            'expired': expired,
        },
    }
    if role in FINANCIAL_ROLES:
        result['monthly_revenue'] = _monthly_revenue(as_of)
    return result


@router.get('/summary')
def get_dashboard_summary(user: dict = Depends(get_current_user)):
    return build_dashboard_summary(user)

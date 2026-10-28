# ==============================================================================
# ROUTERS/CLIENTS.PY — Endpoints de clientes
#
# Maneja todo lo relacionado a clientes (/api/clients/).
#
# Endpoints:
#   GET    /api/clients/        → lista todos los clientes
#   GET    /api/clients/{id}    → detalle de un cliente específico
#   POST   /api/clients/        → crear cliente nuevo
#   PUT    /api/clients/{id}    → editar cliente existente
#   DELETE /api/clients/{id}    → dar de baja un cliente
#
# Reglas de negocio:
#   - Al crear un cliente se copia el base_price del tipo de web.
#   - El total_price = base_price + extra_price.
#   - Los vencimientos se consultan por servicio contratado, desde su vigencia.
#   - El created_by se asigna automáticamente con el token del colaborador.
#   - Soft delete — no se elimina, solo cambia status a 'inactivo'.
# ==============================================================================

from fastapi import HTTPException, status, Depends, Body
from api.router import APIRouter
from typing import Optional
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from api.dependencies import get_current_user
from api.schemas.clients import (ClientCreate, ClientUpdate, ClientResponse, ClientList, ContractedServiceWrite,
                                 CustomerPaymentWrite, PaymentAdjustmentWrite)
from clients.models import (
    Client, WebCatalog, Collaborator, WebFeature, ClientFeature, ClientChangeRequest, ClientHistory,
    ContractedService, ContractedServiceHistory, CustomerPayment, CustomerPaymentAdjustment,
)


router = APIRouter()

CRM_ROLES = ('L1', 'L2', 'L3')
CLIENT_CHANGE_FIELDS = ('name', 'email', 'plan', 'status')


def require_crm_reader(user: dict) -> None:
    if user.get('role') not in CRM_ROLES:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar el CRM')


def request_actor(user: dict) -> Collaborator:
    try:
        return Collaborator.objects.get(pk=user.get('collaborator_id'))
    except (Collaborator.DoesNotExist, ValueError, TypeError):
        raise HTTPException(status_code=401, detail='La sesión no identifica un colaborador válido')


def client_snapshot(client: Client, fields=CLIENT_CHANGE_FIELDS) -> dict:
    return {field: getattr(client, field) for field in fields}


def contracted_service_snapshot(service: ContractedService) -> dict:
    return {
        'client_id': service.client_id, 'service_name': service.service_name,
        'catalog_service_id': service.catalog_service_id,
        'commitment_reference': service.commitment_reference, 'scope': service.scope,
        'agreed_amount': str(service.agreed_amount) if service.agreed_amount is not None else None,
        'currency': service.currency, 'frequency': service.frequency,
        'effective_start': service.effective_start.isoformat() if service.effective_start else None,
        'contracted_duration': service.contracted_duration,
        'documented_expiration': service.documented_expiration.isoformat() if service.documented_expiration else None,
        'terms': service.terms, 'evidence_reference': service.evidence_reference,
    }


def contracted_service_response(service: ContractedService, *, disclose_commercial: bool) -> dict:
    result = contracted_service_snapshot(service)
    history = []
    for event in service.history.all():
        before, after = event.before, event.after
        if not disclose_commercial:
            before = {key: value for key, value in before.items() if key not in {'agreed_amount', 'currency', 'terms'}} if before else None
            after = {key: value for key, value in after.items() if key not in {'agreed_amount', 'currency', 'terms'}}
        history.append({
            'id': event.id, 'actor_id': event.actor_id, 'action': event.action,
            'reason': event.reason, 'impact_assessment': event.impact_assessment if disclose_commercial else None,
            'evidence_reference': event.evidence_reference, 'occurred_at': event.occurred_at,
            'before': before, 'after': after,
        })
    result.update({
        'id': service.id, 'service_name': service.service_name,
        'catalog_service_name': service.catalog_service.name if service.catalog_service_id else None,
        'recorded_by_id': service.recorded_by_id, 'recorded_at': service.recorded_at,
        'history': history,
        'next_due_date': service_next_due_date(service),
        'active_project_id': service.project_links.filter(unlinked_at__isnull=True).values_list('project_id', flat=True).first(),
    })
    if not disclose_commercial:
        result.pop('agreed_amount')
        result.pop('currency')
        result.pop('terms')
    return result


def service_next_due_date(service: ContractedService, as_of: date | None = None) -> date | None:
    if service.frequency == 'unica' or service.effective_start is None:
        return None
    as_of = as_of or timezone.localdate()
    anchor = service.effective_start
    step = relativedelta(months=1) if service.frequency == 'mensual' else relativedelta(years=1)
    period = 1
    due = anchor + step * period
    while due <= as_of:
        period += 1
        due = anchor + step * period
    if service.documented_expiration and (
        service.documented_expiration <= as_of or due > service.documented_expiration
    ):
        return None
    return due


def active_commercial_actor(user: dict) -> Collaborator:
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='El registro y modificación del compromiso corresponde a L2')
    actor = Collaborator.objects.filter(pk=user.get('collaborator_id'), is_active=True, role__level='L2').first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L2 no está activo')
    return actor


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Generar CUPE para cliente
#
# Formato: CLI-XXXXXXXX (CLI + 8 dígitos)
# Usa hash lineal para que el código no sea predecible.
# Fórmula: (id * 7919 + 999999) % 100000000
# Ejemplo: id=1 → CLI-01007918, id=2 → CLI-01015837
# Nunca se repite porque 7919 es número primo.
# ------------------------------------------------------------------------------
def generate_cupe(id: int) -> str:
    code = (id * 7919 + 999999) % 100000000
    return f"CLI-{str(code).zfill(8)}"


def validate_feature_applicability(
    features: list[WebFeature], web_type: WebCatalog
) -> None:
    invalid = []
    for feature in features:
        allowed_type_ids = {item.id for item in feature.web_types.all()}
        if allowed_type_ids and web_type.id not in allowed_type_ids:
            invalid.append(feature.name)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail='Una funcionalidad no aplica al tipo de web seleccionado',
        )


def selected_features(
    feature_ids: list[int], web_type: WebCatalog
) -> list[WebFeature]:
    if len(feature_ids) != len(set(feature_ids)):
        raise HTTPException(status_code=400, detail='Hay funcionalidades duplicadas')
    features = list(
        WebFeature.objects.filter(id__in=feature_ids, is_active=True)
        .prefetch_related('web_types')
    )
    if len(features) != len(feature_ids):
        raise HTTPException(status_code=400, detail='Una funcionalidad no existe o está inactiva')
    validate_feature_applicability(features, web_type)
    return features


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto Django Client a dict
# ------------------------------------------------------------------------------
def client_to_response(client: Client) -> dict:
    domain_price = float(client.domain_price) if client.domain_price is not None else None
    return {
        'id': client.id,
        'cupe': client.cupe,
        'name': client.name,
        'document_type': client.document_type,
        'document_number': client.document_number,
        'phone': client.phone,
        'email': client.email,
        'web_type_id': client.web_type_id,
        'web_type_name': client.web_type.name if client.web_type else None,
        'plan': client.plan,
        'status': client.status,
        'base_price': float(client.base_price) if client.base_price else None,
        'initial_payment': float(client.initial_payment) if client.initial_payment else None,
        'extra_price': float(client.extra_price) if client.extra_price else None,
        'total_price': float(client.total_price) if client.total_price else None,
        'registration_date': client.registration_date,
        'delivery_date': client.delivery_date,
        'next_payment_date': client.next_payment_date,
        'payment_frequency': client.payment_frequency,
        'domain_price': domain_price,
        'domain_price_type': 'ninguno' if not domain_price else ('200' if domain_price == 200 else 'otro'),
        'domain_custom_price': domain_price if domain_price not in (None, 0, 200) else None,
        'features': [
            {
                'id': item.feature_id,
                'name': item.feature.name,
                'extra_price': float(item.feature.extra_price),
            }
            for item in client.features.all()
        ],
        'notes': client.notes,
        'created_by_id': client.created_by_id,
        'created_by_name': f"{client.created_by.first_name} {client.created_by.last_name}" if client.created_by else None,
        'created_at': client.created_at,
        'updated_at': client.updated_at,
    }


# ------------------------------------------------------------------------------
# GET /api/clients/ — Listar todos los clientes
#
# Soporta filtro por status: /api/clients/?status=activo
# Sin filtro → muestra todos.
#
# Respuestas:
#   200 → lista de clientes
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/', response_model=list[ClientResponse])
def get_clients(
    status: Optional[str] = None,
    plan: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    require_crm_reader(user)
    clients = Client.objects.select_related('web_type', 'created_by').prefetch_related('features__feature').all()

    if status:
        clients = clients.filter(status=status)
    if plan:
        clients = clients.filter(plan=plan)
    if search:
        clients = clients.filter(
            Q(name__icontains=search) | Q(cupe__icontains=search)
            | Q(email__icontains=search) | Q(document_number__icontains=search)
        )

    return [client_to_response(c) for c in clients]


# ------------------------------------------------------------------------------
# GET /api/clients/{id} — Detalle de un cliente
#
# Respuestas:
#   200 → datos completos del cliente
#   401 → token inválido
#   404 → cliente no encontrado
# ------------------------------------------------------------------------------
@router.get('/{client_id}', response_model=ClientResponse)
def get_client(
    client_id: int,
    user: dict = Depends(get_current_user)
):
    require_crm_reader(user)
    try:
        client = Client.objects.select_related('web_type', 'created_by').get(id=client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {client_id} no encontrado'
        )

    return client_to_response(client)


# ------------------------------------------------------------------------------
# POST /api/clients/ — Crear cliente nuevo
#
# Al crear:
#   1. Copia el base_price del tipo de web seleccionado
#   2. Calcula total_price = base_price + extra_price (0 al inicio)
#   3. Asigna payment_frequency según el plan
#   4. Calcula next_payment_date si ya tiene delivery_date
#   5. Asigna created_by con el ID del colaborador del token
#   6. Genera el CUPE automáticamente
#
# Respuestas:
#   201 → cliente creado con CUPE asignado
#   400 → ya existe un cliente con ese documento
#   401 → token inválido
#   404 → tipo de web no encontrado
# ------------------------------------------------------------------------------
@router.post('/', response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    user: dict = Depends(get_current_user)
):
    if user.get('role') not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='No tienes permiso para crear clientes')

    # Verificar que no exista otro cliente con el mismo documento
    if Client.objects.filter(document_number=data.document_number).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Ya existe un cliente con el documento {data.document_number}'
        )

    # Verificar que el tipo de web exista y esté activo
    try:
        web_type = WebCatalog.objects.get(id=data.web_type_id)
    except WebCatalog.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Tipo de web con id {data.web_type_id} no encontrado'
        )

    if not web_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'El tipo de web {web_type.name} no está disponible'
        )

    features = selected_features(data.feature_ids, web_type)

    # Obtener el colaborador que está creando el cliente desde el token
    collaborator_id = user.get('collaborator_id')
    created_by = None
    if collaborator_id:
        try:
            created_by = Collaborator.objects.get(id=collaborator_id)
        except Collaborator.DoesNotExist:
            pass

    # Determinar el base_price según el plan
    if data.plan == 'alquiler':
        base_price = web_type.base_price_rent
        payment_frequency = 'mensual'
    elif data.plan == 'venta':
        base_price = web_type.base_price_sale
        payment_frequency = 'anual'
    else:
        raise HTTPException(status_code=400, detail='El plan debe ser alquiler o venta')

    # extra_price empieza en 0 — se suma cuando se asignan funcionalidades
    extra_price = sum((feature.extra_price for feature in features), Decimal('0'))

    # total_price = base_price + extra_price
    total_price = base_price + extra_price

    # Fechas del cliente no acreditan la vigencia de cada servicio.
    next_payment_date = None

    # Crear el cliente en PostgreSQL
    with transaction.atomic():
        try:
            client = Client.objects.create(
                name=data.name,
                document_type=data.document_type,
                document_number=data.document_number,
                phone=data.phone,
                email=data.email,
                web_type=web_type,
                plan=data.plan,
                status=data.status,
                base_price=base_price,
                initial_payment=data.initial_payment,
                extra_price=extra_price,
                total_price=total_price,
                registration_date=data.registration_date,
                delivery_date=data.delivery_date,
                next_payment_date=next_payment_date,
                payment_frequency=payment_frequency,
                domain_price=data.domain_price,
                notes=data.notes,
                created_by=created_by,
            )
        except IntegrityError as exc:
            raise HTTPException(
                status_code=400,
                detail='El documento o CUPE del cliente ya está registrado',
            ) from exc
        client.cupe = generate_cupe(client.id)
        client.save(update_fields=['cupe', 'updated_at'])
        ClientFeature.objects.bulk_create([
            ClientFeature(client=client, feature=feature) for feature in features
        ])
        if created_by:
            ClientHistory.objects.create(
                client=client, actor=created_by, event_type='cliente_creado',
                after_data=client_snapshot(client),
            )

    # Recargar el cliente con las relaciones para la respuesta
    client = Client.objects.select_related('web_type', 'created_by').prefetch_related('features__feature').get(id=client.id)

    return client_to_response(client)


# ------------------------------------------------------------------------------
# PUT /api/clients/{id} — Editar cliente existente
#
# Si se actualiza delivery_date y el cliente pasa a 'activo',
# se recalcula next_payment_date automáticamente.
#
# Respuestas:
#   200 → cliente actualizado
#   401 → token inválido
#   404 → cliente no encontrado
# ------------------------------------------------------------------------------
@router.put('/{client_id}', response_model=ClientResponse)
def update_client(
    client_id: int,
    data: ClientUpdate,
    user: dict = Depends(get_current_user)
):
    require_crm_reader(user)
    raise HTTPException(status_code=409, detail='Los cambios deben solicitarse mediante el flujo de aprobación del CRM')


# ------------------------------------------------------------------------------
# DELETE /api/clients/{id} — Dar de baja un cliente
#
# Soft delete — no borramos, solo cambiamos status a 'inactivo'.
# Así se conserva el historial completo del cliente.
#
# Respuestas:
#   200 → cliente dado de baja
#   401 → token inválido
#   404 → cliente no encontrado
# ------------------------------------------------------------------------------
@router.delete('/{client_id}')
def delete_client(
    client_id: int,
    user: dict = Depends(get_current_user)
):
    require_crm_reader(user)
    raise HTTPException(status_code=409, detail='La baja debe solicitarse mediante el flujo de aprobación del CRM')


@router.post('/{client_id}/change-requests', status_code=201)
def request_client_change(client_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    require_crm_reader(user)
    if user.get('role') not in ('L1', 'L2', 'L3'):
        raise HTTPException(status_code=403, detail='No puedes solicitar cambios')
    proposed = payload.get('changes')
    reason = str(payload.get('reason', '')).strip()
    if not isinstance(proposed, dict) or not proposed or set(proposed) - set(CLIENT_CHANGE_FIELDS):
        raise HTTPException(status_code=422, detail='Indica únicamente nombre, correo, plan o estado')
    if not reason:
        raise HTTPException(status_code=422, detail='El motivo del cambio es obligatorio')
    for field in ('name', 'email'):
        if field in proposed and (not isinstance(proposed[field], str) or not proposed[field].strip()):
            raise HTTPException(status_code=422, detail=f'{field} debe ser un texto no vacío')
        if field == 'name' and field in proposed and len(proposed[field].strip()) < 3:
            raise HTTPException(status_code=422, detail='El nombre debe tener al menos 3 caracteres')
    if 'email' in proposed:
        try:
            validate_email(proposed['email'].strip())
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail='El correo no tiene un formato válido') from exc
        proposed['email'] = proposed['email'].strip()
    if 'name' in proposed:
        proposed['name'] = proposed['name'].strip()
    if 'plan' in proposed and proposed['plan'] not in ('alquiler', 'venta'):
        raise HTTPException(status_code=422, detail='El plan debe ser alquiler o venta')
    if 'status' in proposed and proposed['status'] not in ('desarrollo', 'activo', 'inactivo'):
        raise HTTPException(status_code=422, detail='Estado de cliente inválido')
    actor = request_actor(user)
    with transaction.atomic():
        try:
            client = Client.objects.select_for_update().get(pk=client_id)
        except Client.DoesNotExist:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        before = client_snapshot(client)
        if before['status'] == 'inactivo' or proposed.get('status') == 'inactivo':
            raise HTTPException(status_code=409, detail='El estado inactivo solo puede gestionarse mediante el procedimiento de baja')
        if proposed.get('status') == 'activo' and before['status'] == 'desarrollo' and not client.delivery_date:
            raise HTTPException(status_code=409, detail='La activación requiere la fecha de entrega comercial registrada')
        request = ClientChangeRequest.objects.create(
            client=client, request_type='modificacion', requester=actor,
            reason=reason, proposed_data=proposed, previous_data={key: before[key] for key in proposed},
        )
        ClientHistory.objects.create(
            client=client, request=request, actor=actor, event_type='modificacion_solicitada',
            reason=reason, before_data=before, after_data={**before, **proposed},
        )
    return {'id': request.id, 'status': request.status}


@router.post('/{client_id}/deactivation-requests', status_code=201)
def request_client_deactivation(client_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    require_crm_reader(user)
    reason = str(payload.get('reason', '')).strip()
    if not reason:
        raise HTTPException(status_code=422, detail='El motivo de la baja es obligatorio')
    actor = request_actor(user)
    with transaction.atomic():
        try:
            client = Client.objects.select_for_update().get(pk=client_id)
        except Client.DoesNotExist:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if client.status == 'inactivo':
            raise HTTPException(status_code=409, detail='El cliente ya está inactivo')
        before = client_snapshot(client)
        request = ClientChangeRequest.objects.create(
            client=client, request_type='baja', requester=actor, reason=reason,
            proposed_data={'status': 'inactivo'}, previous_data={'status': client.status},
        )
        ClientHistory.objects.create(
            client=client, request=request, actor=actor, event_type='baja_solicitada',
            reason=reason, before_data=before, after_data={**before, 'status': 'inactivo'},
        )
    return {'id': request.id, 'status': request.status}


@router.get('/requests/pending')
def list_client_requests(user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='No tienes permiso para resolver solicitudes')
    requests = ClientChangeRequest.objects.filter(status='pendiente').select_related('client', 'requester')
    if role == 'L2':
        requests = requests.filter(request_type='modificacion')
    return [{
        'id': item.id, 'client_id': item.client_id, 'client_name': item.client.name,
        'request_type': item.request_type, 'requester_id': item.requester_id,
        'requested_at': item.requested_at, 'reason': item.reason,
        'proposed_data': item.proposed_data, 'previous_data': item.previous_data,
    } for item in requests]


@router.post('/requests/{request_id}/resolve')
def resolve_client_request(request_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    role = user.get('role')
    decision = payload.get('decision')
    resolution_reason = str(payload.get('reason', '')).strip()
    if decision not in ('aprobado', 'rechazado') or not resolution_reason:
        raise HTTPException(status_code=422, detail='Indica una decisión y su motivo')
    actor = request_actor(user)
    with transaction.atomic():
        try:
            item = ClientChangeRequest.objects.select_for_update().select_related('client').get(pk=request_id)
            client = Client.objects.select_for_update().get(pk=item.client_id)
        except ClientChangeRequest.DoesNotExist:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        allowed = role in ('L1', 'L2') if item.request_type == 'modificacion' else role == 'L1'
        if not allowed:
            raise HTTPException(status_code=403, detail='No tienes competencia para resolver esta solicitud')
        if item.status != 'pendiente':
            raise HTTPException(status_code=409, detail='La solicitud ya fue resuelta')
        before = client_snapshot(client)
        event = f'{item.request_type}_rechazada'
        if decision == 'aprobado':
            if any(before.get(key) != value for key, value in item.previous_data.items()):
                raise HTTPException(status_code=409, detail='El cliente cambió desde la solicitud; debe revisarse nuevamente')
            if item.request_type == 'baja':
                client.status = 'inactivo'
                client.save(update_fields=['status', 'updated_at'])
            else:
                changes = item.proposed_data
                if 'status' in changes and (before['status'] == 'inactivo' or changes['status'] == 'inactivo'):
                    raise HTTPException(status_code=409, detail='El estado inactivo requiere el procedimiento de baja')
                if changes.get('status') == 'activo' and before['status'] == 'desarrollo' and not client.delivery_date:
                    raise HTTPException(status_code=409, detail='La activación requiere fecha de entrega registrada')
                for field, value in changes.items():
                    setattr(client, field, value)
                if 'plan' in changes:
                    client.payment_frequency = 'mensual' if client.plan == 'alquiler' else 'anual'
                    client.base_price = client.web_type.base_price_rent if client.plan == 'alquiler' else client.web_type.base_price_sale
                    selected = [item.feature for item in client.features.select_related('feature')]
                    client.extra_price = sum((feature.extra_price for feature in selected), Decimal('0'))
                    client.total_price = client.base_price + client.extra_price
                client.save()
            event = f'{item.request_type}_aprobada'
        after = client_snapshot(client)
        item.status = decision
        item.resolved_by = actor
        item.resolved_at = timezone.now()
        item.resolution_reason = resolution_reason
        item.save(update_fields=['status', 'resolved_by', 'resolved_at', 'resolution_reason'])
        ClientHistory.objects.create(
            client=client, request=item, actor=actor, event_type=event,
            reason=resolution_reason, before_data=before, after_data=after,
        )
    return {'id': item.id, 'status': item.status}


@router.get('/{client_id}/history')
def get_client_history(client_id: int, user: dict = Depends(get_current_user)):
    require_crm_reader(user)
    if not Client.objects.filter(pk=client_id).exists():
        raise HTTPException(status_code=404, detail='Cliente no encontrado')
    return list(ClientHistory.objects.filter(client_id=client_id).values(
        'id', 'request_id', 'actor_id', 'event_type', 'occurred_at', 'reason', 'before_data', 'after_data',
    ))


@router.get('/{client_id}/contracted-services')
def list_contracted_services(client_id: int, user: dict = Depends(get_current_user)):
    require_crm_reader(user)
    if not Client.objects.filter(pk=client_id).exists():
        raise HTTPException(status_code=404, detail='Cliente no encontrado')
    disclose_commercial = user.get('role') in ('L1', 'L2')
    services = ContractedService.objects.filter(client_id=client_id).select_related('catalog_service', 'recorded_by').prefetch_related('history')
    return [contracted_service_response(item, disclose_commercial=disclose_commercial) for item in services]


@router.post('/{client_id}/contracted-services', status_code=status.HTTP_201_CREATED)
def record_contracted_service(
    client_id: int, payload: ContractedServiceWrite, user: dict = Depends(get_current_user),
):
    actor = active_commercial_actor(user)
    with transaction.atomic():
        client = Client.objects.select_for_update().filter(pk=client_id).first()
        if client is None:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if client.status == 'inactivo':
            raise HTTPException(status_code=409, detail='Un cliente inactivo requiere regularización comercial antes de una nueva contratación')
        catalog_service = WebCatalog.objects.filter(pk=payload.catalog_service_id, is_active=True).first() if payload.catalog_service_id else None
        if payload.catalog_service_id and catalog_service is None:
            raise HTTPException(status_code=400, detail='La oferta no existe o no está disponible para una nueva contratación')
        values = payload.model_dump(exclude={'reason', 'impact_assessment', 'catalog_service_id'})
        service = ContractedService.objects.create(
            client=client, catalog_service=catalog_service, recorded_by=actor, **values,
        )
        snapshot = contracted_service_snapshot(service)
        ContractedServiceHistory.objects.create(
            service=service, actor=actor, action='registro', after=snapshot,
            reason=payload.reason.strip(), evidence_reference=service.evidence_reference,
        )
    return contracted_service_response(service, disclose_commercial=True)


@router.put('/{client_id}/contracted-services/{service_id}')
def amend_contracted_service(
    client_id: int, service_id: int, payload: ContractedServiceWrite, user: dict = Depends(get_current_user),
):
    actor = active_commercial_actor(user)
    with transaction.atomic():
        service = ContractedService.objects.select_for_update(of=('self',)).select_related('client', 'catalog_service').filter(
            pk=service_id, client_id=client_id,
        ).first()
        if service is None:
            raise HTTPException(status_code=404, detail='Servicio contratado no encontrado para este cliente')
        before = contracted_service_snapshot(service)
        catalog_service = WebCatalog.objects.filter(pk=payload.catalog_service_id).first() if payload.catalog_service_id else None
        if payload.catalog_service_id and (catalog_service is None or (catalog_service.pk != service.catalog_service_id and not catalog_service.is_active)):
            raise HTTPException(status_code=400, detail='La oferta no existe o no está disponible para el cambio')
        if not payload.impact_assessment.strip():
            raise HTTPException(status_code=422, detail='La modificación requiere evaluar las obligaciones afectadas')
        values = payload.model_dump(exclude={'reason', 'impact_assessment', 'catalog_service_id'})
        for field, value in values.items():
            setattr(service, field, value)
        service.catalog_service = catalog_service
        service.save()
        ContractedServiceHistory.objects.create(
            service=service, actor=actor, action='modificacion', before=before,
            after=contracted_service_snapshot(service), reason=payload.reason.strip(),
            evidence_reference=service.evidence_reference, impact_assessment=payload.impact_assessment.strip(),
        )
    return contracted_service_response(service, disclose_commercial=True)


def payment_actor(user: dict) -> Collaborator:
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='La gestión de cobros corresponde a L2')
    actor = Collaborator.objects.filter(pk=user.get('collaborator_id'), is_active=True, role__level='L2').first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L2 no está activo')
    return actor


def payment_json(item: CustomerPayment) -> dict:
    adjustments = list(item.adjustments.order_by('id').values(
        'id', 'amount', 'reason', 'evidence_reference', 'recorded_by_id', 'recorded_at',
        'confirmed_by_id', 'confirmed_at',
    ))
    confirmed_total = (item.amount if item.confirmed_at else Decimal('0')) + sum(
        item.adjustments.filter(confirmed_at__isnull=False).values_list('amount', flat=True), Decimal('0'))
    return {
        'id': item.id, 'client_id': item.client_id, 'service_id': item.service_id,
        'reference': item.reference, 'amount': item.amount, 'currency': item.currency,
        'effective_date': item.effective_date, 'evidence_reference': item.evidence_reference,
        'recorded_by_id': item.recorded_by_id, 'recorded_at': item.recorded_at,
        'confirmed_by_id': item.confirmed_by_id, 'confirmed_at': item.confirmed_at,
        'confirmation_evidence': item.confirmation_evidence,
        'adjustments': adjustments, 'confirmed_net': confirmed_total,
    }


@router.get('/{client_id}/payments')
def list_client_payments(client_id: int, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='No tienes acceso a información financiera')
    if not Collaborator.objects.filter(pk=user.get('collaborator_id'), is_active=True, role__level=role).exists():
        raise HTTPException(status_code=403, detail='El colaborador no está activo')
    if not Client.objects.filter(pk=client_id).exists():
        raise HTTPException(status_code=404, detail='Cliente no encontrado')
    return [payment_json(item) for item in CustomerPayment.objects.filter(client_id=client_id).prefetch_related('adjustments')]


@router.post('/{client_id}/payments', status_code=status.HTTP_201_CREATED)
def record_client_payment(client_id: int, payload: CustomerPaymentWrite, user: dict = Depends(get_current_user)):
    actor = payment_actor(user)
    try:
        with transaction.atomic():
            client = Client.objects.select_for_update().filter(pk=client_id).first()
            if client is None:
                raise HTTPException(status_code=404, detail='Cliente no encontrado')
            service = ContractedService.objects.select_for_update().filter(pk=payload.service_id, client=client).first()
            if service is None:
                raise HTTPException(status_code=409, detail='El compromiso no corresponde al cliente')
            if service.agreed_amount is None or not service.currency:
                raise HTTPException(status_code=409, detail='El compromiso debe acreditar importe y moneda')
            if payload.currency != service.currency.upper():
                raise HTTPException(status_code=409, detail='La moneda debe coincidir con el compromiso')
            item = CustomerPayment.objects.create(
                client=client, service=service, recorded_by=actor,
                reference=payload.reference, amount=payload.amount, currency=payload.currency,
                effective_date=payload.effective_date, evidence_reference=payload.evidence_reference,
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La referencia de cobro ya existe para este cliente')
    return payment_json(item)


@router.post('/payments/{payment_id}/confirm')
def confirm_client_payment(payment_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    actor = payment_actor(user)
    evidence = str(payload.get('evidence_reference', '')).strip()
    if not evidence:
        raise HTTPException(status_code=422, detail='La confirmación requiere evidencia')
    with transaction.atomic():
        item = CustomerPayment.objects.select_for_update().select_related('service').filter(pk=payment_id).first()
        if item is None:
            raise HTTPException(status_code=404, detail='Cobro no encontrado')
        if item.confirmed_at:
            raise HTTPException(status_code=409, detail='El cobro ya fue confirmado')
        if item.amount <= 0 or item.currency != item.service.currency.upper():
            raise HTTPException(status_code=409, detail='El cobro no coincide con el compromiso')
        item.confirmed_by, item.confirmed_at, item.confirmation_evidence = actor, timezone.now(), evidence
        item.save(update_fields=['confirmed_by', 'confirmed_at', 'confirmation_evidence'])
    return payment_json(item)


@router.post('/payments/{payment_id}/adjustments', status_code=status.HTTP_201_CREATED)
def record_payment_adjustment(payment_id: int, payload: PaymentAdjustmentWrite, user: dict = Depends(get_current_user)):
    actor = payment_actor(user)
    with transaction.atomic():
        item = CustomerPayment.objects.select_for_update().filter(pk=payment_id).first()
        if item is None:
            raise HTTPException(status_code=404, detail='Cobro no encontrado')
        if not item.confirmed_at:
            raise HTTPException(status_code=409, detail='Solo se corrige un cobro confirmado')
        current = item.amount + sum(item.adjustments.filter(confirmed_at__isnull=False).values_list('amount', flat=True), Decimal('0'))
        if current + payload.amount < 0:
            raise HTTPException(status_code=409, detail='El ajuste no puede producir un neto negativo')
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=item, amount=payload.amount, reason=payload.reason,
            evidence_reference=payload.evidence_reference, recorded_by=actor,
        )
    return {'id': adjustment.id, 'payment_id': payment_id, 'amount': adjustment.amount,
            'recorded_by_id': actor.id, 'recorded_at': adjustment.recorded_at}


@router.post('/payments/adjustments/{adjustment_id}/confirm')
def confirm_payment_adjustment(adjustment_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    actor = payment_actor(user)
    with transaction.atomic():
        adjustment = CustomerPaymentAdjustment.objects.select_for_update().select_related('payment').filter(pk=adjustment_id).first()
        if adjustment is None:
            raise HTTPException(status_code=404, detail='Ajuste no encontrado')
        if adjustment.confirmed_at:
            raise HTTPException(status_code=409, detail='El ajuste ya fue confirmado')
        payment = CustomerPayment.objects.select_for_update().get(pk=adjustment.payment_id)
        net = payment.amount + sum(payment.adjustments.filter(confirmed_at__isnull=False).values_list('amount', flat=True), Decimal('0'))
        if net + adjustment.amount < 0:
            raise HTTPException(status_code=409, detail='El ajuste produciría un neto negativo')
        adjustment.confirmed_by, adjustment.confirmed_at = actor, timezone.now()
        adjustment.save(update_fields=['confirmed_by', 'confirmed_at'])
    return {'id': adjustment.id, 'payment_id': adjustment.payment_id, 'confirmed_by_id': actor.id,
            'confirmed_at': adjustment.confirmed_at, 'amount': adjustment.amount}

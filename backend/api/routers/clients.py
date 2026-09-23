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
#   - El next_payment_date se calcula automáticamente según el plan.
#   - El created_by se asigna automáticamente con el token del colaborador.
#   - Soft delete — no se elimina, solo cambia status a 'inactivo'.
# ==============================================================================

from fastapi import HTTPException, status, Depends
from api.router import APIRouter
from typing import Optional
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from api.dependencies import get_current_user
from api.schemas.clients import ClientCreate, ClientUpdate, ClientResponse, ClientList
from clients.models import Client, WebCatalog, Collaborator, WebFeature, ClientFeature


router = APIRouter()


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


def selected_features(feature_ids: list[int]) -> list[WebFeature]:
    if len(feature_ids) != len(set(feature_ids)):
        raise HTTPException(status_code=400, detail='Hay funcionalidades duplicadas')
    features = list(WebFeature.objects.filter(id__in=feature_ids, is_active=True))
    if len(features) != len(feature_ids):
        raise HTTPException(status_code=400, detail='Una funcionalidad no existe o está inactiva')
    return features


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Calcular next_payment_date
#
# Lógica según el plan:
#   - Mensual (alquiler): mismo día del mes siguiente a delivery_date
#   - Anual (venta): mismo día y mes del año siguiente a registration_date
# ------------------------------------------------------------------------------
def calculate_next_payment(
    payment_frequency: str,
    delivery_date: date = None,
    registration_date: date = None
) -> date:
    if payment_frequency == 'mensual' and delivery_date:
        # Suma un mes a delivery_date conservando el mismo día
        return delivery_date + relativedelta(months=1)
    elif payment_frequency == 'anual' and registration_date:
        # Suma un año a registration_date conservando día y mes
        return registration_date + relativedelta(years=1)
    return None


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
    if user.get('role') not in ('L1', 'L2', 'L3', 'L4'):
        raise HTTPException(status_code=403, detail='No tienes permiso para crear clientes')

    features = selected_features(data.feature_ids)

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

    # Calcular next_payment_date si ya tiene delivery_date
    next_payment_date = None
    if data.delivery_date:
        next_payment_date = calculate_next_payment(
            payment_frequency,
            delivery_date=data.delivery_date,
            registration_date=data.registration_date
        )

    # Crear el cliente en PostgreSQL
    with transaction.atomic():
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
        client.cupe = generate_cupe(client.id)
        client.save(update_fields=['cupe', 'updated_at'])
        ClientFeature.objects.bulk_create([
            ClientFeature(client=client, feature=feature) for feature in features
        ])

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
    if user.get('role') not in ('L1', 'L2', 'L3', 'L4'):
        raise HTTPException(status_code=403, detail='No tienes permiso para editar clientes')

    try:
        client = Client.objects.select_related('web_type', 'created_by').get(id=client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {client_id} no encontrado'
        )

    update_data = data.model_dump(exclude_unset=True)
    feature_ids = update_data.pop('feature_ids', None)
    features = selected_features(feature_ids) if feature_ids is not None else None
    for calculated_field in ('base_price', 'extra_price', 'total_price', 'payment_frequency', 'next_payment_date'):
        update_data.pop(calculated_field, None)

    with transaction.atomic():
        for field, value in update_data.items():
            if field == 'web_type_id':
                try:
                    client.web_type = WebCatalog.objects.get(id=value, is_active=True)
                except WebCatalog.DoesNotExist:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f'Tipo de web con id {value} no encontrado'
                    )
            else:
                setattr(client, field, value)

        if client.plan not in ('alquiler', 'venta'):
            raise HTTPException(status_code=400, detail='El plan debe ser alquiler o venta')
        client.payment_frequency = 'mensual' if client.plan == 'alquiler' else 'anual'
        client.base_price = (
            client.web_type.base_price_rent if client.plan == 'alquiler'
            else client.web_type.base_price_sale
        )
        if features is not None:
            ClientFeature.objects.filter(client=client).delete()
            ClientFeature.objects.bulk_create([
                ClientFeature(client=client, feature=feature) for feature in features
            ])
            selected = features
        else:
            selected = [item.feature for item in client.features.select_related('feature')]
        client.extra_price = sum((feature.extra_price for feature in selected), Decimal('0'))
        client.total_price = client.base_price + client.extra_price

        if any(field in update_data for field in ('delivery_date', 'registration_date', 'plan')):
            client.next_payment_date = calculate_next_payment(
                client.payment_frequency,
                delivery_date=client.delivery_date,
                registration_date=client.registration_date
            )
            if client.delivery_date and client.status == 'desarrollo':
                client.status = 'activo'

        client.save()

    client = Client.objects.select_related('web_type', 'created_by').prefetch_related('features__feature').get(id=client.id)
    return client_to_response(client)


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
    if user.get('role') not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='No tienes permiso para desactivar clientes')
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {client_id} no encontrado'
        )

    # Soft delete — no borramos, solo desactivamos
    client.status = 'inactivo'
    client.save()

    return {'message': f'Cliente {client.cupe} dado de baja correctamente'}

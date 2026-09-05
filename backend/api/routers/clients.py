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

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from api.dependencies import get_current_user
from api.schemas.clients import ClientCreate, ClientUpdate, ClientResponse, ClientList
from clients.models import Client, WebCatalog, Collaborator


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
        'domain_price': float(client.domain_price) if client.domain_price is not None else None,
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
@router.get('/', response_model=list[ClientList])
def get_clients(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    clients = Client.objects.select_related('web_type').all()

    if status:
        clients = clients.filter(status=status)

    return [
        {
            'id': c.id,
            'cupe': c.cupe,
            'name': c.name,
            'document_type': c.document_type,
            'document_number': c.document_number,
            'web_type_name': c.web_type.name if c.web_type else None,
            'plan': c.plan,
            'status': c.status,
            'next_payment_date': c.next_payment_date,
            'total_price': float(c.total_price) if c.total_price else None,
        }
        for c in clients
    ]


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
        base_price = data.base_price or float(web_type.base_price_rent)
        payment_frequency = 'mensual'
    else:
        base_price = data.base_price or float(web_type.base_price_sale)
        payment_frequency = 'anual'

    # extra_price empieza en 0 — se suma cuando se asignan funcionalidades
    extra_price = 0.00

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

    # Generar CUPE usando el ID que Django asignó automáticamente
    client.cupe = generate_cupe(client.id)
    client.save()

    # Recargar el cliente con las relaciones para la respuesta
    client = Client.objects.select_related('web_type', 'created_by').get(id=client.id)

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
    try:
        client = Client.objects.select_related('web_type', 'created_by').get(id=client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {client_id} no encontrado'
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == 'web_type_id':
            try:
                client.web_type = WebCatalog.objects.get(id=value)
            except WebCatalog.DoesNotExist:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Tipo de web con id {value} no encontrado'
                )
        else:
            setattr(client, field, value)

    # Si se actualizó delivery_date, recalcular next_payment_date
    if 'delivery_date' in update_data and client.delivery_date:
        client.next_payment_date = calculate_next_payment(
            client.payment_frequency,
            delivery_date=client.delivery_date,
            registration_date=client.registration_date
        )
        # Si la web fue entregada y el status sigue en desarrollo, cambiarlo a activo
        if client.status == 'desarrollo':
            client.status = 'activo'

    client.save()

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
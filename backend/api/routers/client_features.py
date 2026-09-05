# ==============================================================================
# ROUTERS/CLIENT_FEATURES.PY — Endpoints de funcionalidades de clientes
#
# Maneja la asignación y gestión de funcionalidades extra por cliente.
#
# Endpoints:
#   GET    /api/client-features/client/{client_id} → funcionalidades de un cliente
#   POST   /api/client-features/                   → asignar funcionalidad a cliente
#   DELETE /api/client-features/{id}               → quitar funcionalidad de cliente
#
# Reglas de negocio:
#   - Al asignar una funcionalidad se suma su precio al extra_price del cliente
#     y se recalcula el total_price automáticamente.
#   - Al quitar una funcionalidad se resta su precio del extra_price del cliente
#     y se recalcula el total_price automáticamente.
#   - Solo L1 a L4 pueden asignar o quitar funcionalidades.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional

from api.dependencies import get_current_user
from api.schemas.client_features import (
    ClientFeatureCreate,
    ClientFeatureResponse,
    ClientFeatureList
)
from clients.models import Client, WebFeature, ClientFeature


router = APIRouter()


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Verificar que el usuario puede gestionar funcionalidades
#
# Solo L1 a L4 pueden asignar o quitar funcionalidades.
# L5 (Developer) solo puede consultar.
# ------------------------------------------------------------------------------
def require_can_manage(user: dict):
    role = user.get('role')
    if role not in ['L1', 'L2', 'L3', 'L4']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No tienes permiso para gestionar funcionalidades'
        )


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto ClientFeature a dict
# ------------------------------------------------------------------------------
def feature_to_response(cf: ClientFeature) -> dict:
    return {
        'id': cf.id,
        'client_id': cf.client_id,
        'client_name': cf.client.name if cf.client else None,
        'client_cupe': cf.client.cupe if cf.client else None,
        'feature_id': cf.feature_id,
        'feature_name': cf.feature.name if cf.feature else None,
        'feature_price': float(cf.feature.extra_price) if cf.feature else None,
        'added_at': cf.added_at,
    }


# ------------------------------------------------------------------------------
# GET /api/client-features/client/{client_id}
# Lista todas las funcionalidades de un cliente específico
#
# Respuestas:
#   200 → lista de funcionalidades del cliente
#   401 → token inválido
#   404 → cliente no encontrado
# ------------------------------------------------------------------------------
@router.get('/client/{client_id}', response_model=list[ClientFeatureList])
def get_client_features(
    client_id: int,
    user: dict = Depends(get_current_user)
):
    # Verificar que el cliente exista
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {client_id} no encontrado'
        )

    # Traer todas las funcionalidades del cliente
    # select_related precarga feature para no hacer consulta extra por cada una
    client_features = ClientFeature.objects.select_related('feature').filter(
        client=client
    )

    return [
        {
            'id': cf.id,
            'feature_id': cf.feature_id,
            'feature_name': cf.feature.name if cf.feature else None,
            'feature_price': float(cf.feature.extra_price) if cf.feature else None,
            'added_at': cf.added_at,
        }
        for cf in client_features
    ]


# ------------------------------------------------------------------------------
# POST /api/client-features/ — Asignar funcionalidad a un cliente
#
# Al asignar:
#   1. Crea el registro en client_features
#   2. Suma el extra_price de la funcionalidad al extra_price del cliente
#   3. Recalcula el total_price del cliente
#
# Respuestas:
#   201 → funcionalidad asignada correctamente
#   400 → el cliente ya tiene esa funcionalidad
#   401 → token inválido
#   403 → no tiene permiso
#   404 → cliente o funcionalidad no encontrada
# ------------------------------------------------------------------------------
@router.post('/', response_model=ClientFeatureResponse, status_code=status.HTTP_201_CREATED)
def assign_feature(
    data: ClientFeatureCreate,
    user: dict = Depends(get_current_user)
):
    require_can_manage(user)

    # Verificar que el cliente exista
    try:
        client = Client.objects.get(id=data.client_id)
    except Client.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Cliente con id {data.client_id} no encontrado'
        )

    # Verificar que la funcionalidad exista y esté activa
    try:
        feature = WebFeature.objects.get(id=data.feature_id)
    except WebFeature.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Funcionalidad con id {data.feature_id} no encontrada'
        )

    if not feature.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'La funcionalidad {feature.name} no está disponible'
        )

    # Verificar que el cliente no tenga ya esa funcionalidad
    if ClientFeature.objects.filter(client=client, feature=feature).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'El cliente ya tiene la funcionalidad {feature.name}'
        )

    # Crear el registro en client_features
    client_feature = ClientFeature.objects.create(
        client=client,
        feature=feature
    )

    # Actualizar extra_price y total_price del cliente
    # extra_price actual + precio de la nueva funcionalidad
    current_extra = client.extra_price or 0
    client.extra_price = current_extra + feature.extra_price

    # total_price = base_price + extra_price
    base = client.base_price or 0
    client.total_price = base + client.extra_price
    client.save()

    return feature_to_response(client_feature)


# ------------------------------------------------------------------------------
# DELETE /api/client-features/{id} — Quitar funcionalidad de un cliente
#
# Al quitar:
#   1. Elimina el registro de client_features
#   2. Resta el extra_price de la funcionalidad del extra_price del cliente
#   3. Recalcula el total_price del cliente
#
# Respuestas:
#   200 → funcionalidad quitada correctamente
#   401 → token inválido
#   403 → no tiene permiso
#   404 → registro no encontrado
# ------------------------------------------------------------------------------
@router.delete('/{client_feature_id}')
def remove_feature(
    client_feature_id: int,
    user: dict = Depends(get_current_user)
):
    require_can_manage(user)

    # Buscar el registro
    try:
        client_feature = ClientFeature.objects.select_related(
            'client', 'feature'
        ).get(id=client_feature_id)
    except ClientFeature.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Registro con id {client_feature_id} no encontrado'
        )

    # Guardar referencias antes de eliminar
    client = client_feature.client
    feature = client_feature.feature

    # Eliminar el registro
    client_feature.delete()

    # Restar el precio de la funcionalidad del extra_price del cliente
    current_extra = client.extra_price or 0
    client.extra_price = max(0, current_extra - feature.extra_price)

    # Recalcular total_price
    base = client.base_price or 0
    client.total_price = base + client.extra_price
    client.save()

    return {'message': f'Funcionalidad {feature.name} quitada del cliente {client.cupe}'}
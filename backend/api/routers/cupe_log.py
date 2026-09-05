# ==============================================================================
# ROUTERS/CUPE_LOG.PY — Endpoints del historial de cambios de CUPE
#
# Maneja todo lo relacionado al historial de cambios de CUPE.
#
# Endpoints:
#   GET  /api/cupe-log/              → lista todo el historial
#   GET  /api/cupe-log/{id}          → detalle de un cambio específico
#   POST /api/cupe-log/              → solicitar cambio de CUPE (solo Superadmin)
#
# Reglas de negocio:
#   - Solo el Superadmin (L1) puede autorizar cambios de CUPE.
#   - Al aprobar un cambio, el sistema actualiza el CUPE en la tabla
#     original (clients o collaborators) y registra el cambio aquí
#     en una sola transacción atómica.
#   - Los logs nunca se editan ni se eliminan — son de solo lectura.
#   - El old_cupe se obtiene automáticamente de la BD, no lo manda React.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from django.db import transaction

from api.dependencies import get_current_user
from api.schemas.cupe_log import CupeLogCreate, CupeLogResponse, CupeLogList
from clients.models import CupeLog, Client, Collaborator


router = APIRouter()


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Verificar que el usuario sea Superadmin (L1)
#
# Solo Superadmin puede autorizar cambios de CUPE.
# ------------------------------------------------------------------------------
def require_superadmin(user: dict):
    if user.get('role') != 'L1':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Solo el Superadmin puede autorizar cambios de CUPE'
        )


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto CupeLog a dict
# ------------------------------------------------------------------------------
def log_to_response(log: CupeLog) -> dict:
    return {
        'id': log.id,
        'entity_type': log.entity_type,
        'entity_id': log.entity_id,
        'old_cupe': log.old_cupe,
        'new_cupe': log.new_cupe,
        'reason': log.reason,
        'observations': log.observations,
        'changed_by_id': log.changed_by_id,
        # Nombre completo del colaborador que solicitó el cambio
        'changed_by_name': (
            f"{log.changed_by.first_name} {log.changed_by.last_name}"
            if log.changed_by else None
        ),
        'authorized_by_id': log.authorized_by_id,
        # Nombre completo del Superadmin que autorizó
        'authorized_by_name': (
            f"{log.authorized_by.first_name} {log.authorized_by.last_name}"
            if log.authorized_by else None
        ),
        'changed_at': log.changed_at,
    }


# ------------------------------------------------------------------------------
# GET /api/cupe-log/ — Listar todo el historial de cambios
#
# Cualquier colaborador autenticado puede ver el historial.
# Soporta filtro por entity_type: /api/cupe-log/?entity_type=client
#
# Respuestas:
#   200 → lista del historial ordenado por fecha (más reciente primero)
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/', response_model=list[CupeLogList])
def get_cupe_logs(
    entity_type: str = None,  # Filtro opcional: 'client' o 'collaborator'
    user: dict = Depends(get_current_user)
):
    logs = CupeLog.objects.select_related('changed_by', 'authorized_by').all()

    if entity_type:
        logs = logs.filter(entity_type=entity_type)

    return [
        {
            'id': log.id,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'old_cupe': log.old_cupe,
            'new_cupe': log.new_cupe,
            'reason': log.reason,
            'changed_by_name': (
                f"{log.changed_by.first_name} {log.changed_by.last_name}"
                if log.changed_by else None
            ),
            'authorized_by_name': (
                f"{log.authorized_by.first_name} {log.authorized_by.last_name}"
                if log.authorized_by else None
            ),
            'changed_at': log.changed_at,
        }
        for log in logs
    ]


# ------------------------------------------------------------------------------
# GET /api/cupe-log/{id} — Detalle de un cambio específico
#
# Respuestas:
#   200 → datos completos del cambio
#   401 → token inválido
#   404 → registro no encontrado
# ------------------------------------------------------------------------------
@router.get('/{log_id}', response_model=CupeLogResponse)
def get_cupe_log(
    log_id: int,
    user: dict = Depends(get_current_user)
):
    try:
        log = CupeLog.objects.select_related('changed_by', 'authorized_by').get(id=log_id)
    except CupeLog.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Registro con id {log_id} no encontrado'
        )

    return log_to_response(log)


# ------------------------------------------------------------------------------
# POST /api/cupe-log/ — Solicitar y autorizar cambio de CUPE
#
# Solo Superadmin puede hacer esto.
#
# El proceso en una sola transacción atómica:
#   1. Busca el cliente o colaborador por entity_id
#   2. Obtiene el old_cupe actual
#   3. Verifica que el new_cupe no esté en uso
#   4. Actualiza el CUPE en la tabla original
#   5. Registra el cambio en cupe_logs
#
# Si algo falla, toda la operación se revierte (transacción atómica).
#
# Respuestas:
#   201 → CUPE cambiado y registrado correctamente
#   400 → el new_cupe ya está en uso
#   401 → token inválido
#   403 → no es Superadmin
#   404 → cliente o colaborador no encontrado
# ------------------------------------------------------------------------------
@router.post('/', response_model=CupeLogResponse, status_code=status.HTTP_201_CREATED)
def change_cupe(
    data: CupeLogCreate,
    user: dict = Depends(get_current_user)
):
    # Solo Superadmin puede autorizar cambios de CUPE
    require_superadmin(user)

    # Obtener el Superadmin que está haciendo el cambio desde el token
    collaborator_id = user.get('collaborator_id')
    try:
        superadmin = Collaborator.objects.get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='No se encontró el colaborador autenticado'
        )

    # Usar transacción atómica — si algo falla, todo se revierte
    with transaction.atomic():

        if data.entity_type == 'client':
            # Buscar el cliente
            try:
                entity = Client.objects.get(id=data.entity_id)
            except Client.DoesNotExist:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f'Cliente con id {data.entity_id} no encontrado'
                )

            # Verificar que el nuevo CUPE no esté en uso por otro cliente
            if Client.objects.filter(cupe=data.new_cupe).exclude(id=data.entity_id).exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'El CUPE {data.new_cupe} ya está en uso por otro cliente'
                )

            # Guardar el CUPE anterior y actualizar
            old_cupe = entity.cupe
            entity.cupe = data.new_cupe
            entity.save()

        elif data.entity_type == 'collaborator':
            # Buscar el colaborador
            try:
                entity = Collaborator.objects.get(id=data.entity_id)
            except Collaborator.DoesNotExist:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f'Colaborador con id {data.entity_id} no encontrado'
                )

            # Verificar que el nuevo CUPE no esté en uso por otro colaborador
            if Collaborator.objects.filter(cupe=data.new_cupe).exclude(id=data.entity_id).exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'El CUPE {data.new_cupe} ya está en uso por otro colaborador'
                )

            # Guardar el CUPE anterior y actualizar
            old_cupe = entity.cupe
            entity.cupe = data.new_cupe
            entity.save()

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='entity_type debe ser "client" o "collaborator"'
            )

        # Registrar el cambio en cupe_logs
        log = CupeLog.objects.create(
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            old_cupe=old_cupe,
            new_cupe=data.new_cupe,
            reason=data.reason,
            observations=data.observations,
            # El que solicita y autoriza es el mismo Superadmin
            changed_by=superadmin,
            authorized_by=superadmin,
        )

    # Recargar el log con las relaciones para la respuesta
    log = CupeLog.objects.select_related('changed_by', 'authorized_by').get(id=log.id)

    return log_to_response(log)
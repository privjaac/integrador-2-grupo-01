# ==============================================================================
# ROUTERS/WEB_TYPES.PY — Endpoints del catálogo de tipos de web
#
# Maneja todo lo relacionado al catálogo (/api/web-types/).
#
# Endpoints:
#   GET    /api/web-types/       → lista todos los tipos de web
#   GET    /api/web-types/{id}   → detalle de un tipo de web específico
#   POST   /api/web-types/       → crear tipo de web nuevo (solo Superadmin)
#   PUT    /api/web-types/{id}   → editar tipo de web existente (solo Superadmin)
#   DELETE /api/web-types/{id}   → eliminar tipo de web (solo Superadmin)
#
# Reglas de negocio:
#   - Solo Superadmin (L1) puede crear, editar y eliminar tipos de web.
#   - No se puede eliminar un tipo de web si tiene clientes asignados.
#   - Cualquier colaborador autenticado puede ver el catálogo.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional

from api.dependencies import get_current_user
from api.schemas.web_types import WebCatalogCreate, WebCatalogUpdate, WebCatalogResponse
from clients.models import WebCatalog


router = APIRouter()


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Verificar que el usuario sea Superadmin (L1)
# ------------------------------------------------------------------------------
def require_superadmin(user: dict):
    if user.get('role') != 'L1':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Solo el Superadmin puede realizar esta acción'
        )


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto Django WebCatalog a dict
# ------------------------------------------------------------------------------
def web_type_to_response(web_type: WebCatalog) -> dict:
    return {
        'id': web_type.id,
        'name': web_type.name,
        'base_price_rent': float(web_type.base_price_rent),
        'base_price_sale': float(web_type.base_price_sale),
        'is_active': web_type.is_active,
        # Contar cuántos clientes tienen este tipo de web asignado
        'clients_count': web_type.clients.count(),
        'created_at': web_type.created_at,
    }


# ------------------------------------------------------------------------------
# GET /api/web-types/ — Listar todos los tipos de web
#
# Soporta filtro por is_active: /api/web-types/?is_active=true
# Sin filtro → muestra todos.
#
# Respuestas:
#   200 → lista de tipos de web
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/', response_model=list[WebCatalogResponse])
def get_web_types(
    is_active: Optional[bool] = None,  # None → muestra todos
    user: dict = Depends(get_current_user)
):
    web_types = WebCatalog.objects.all()

    # is not None → permite filtrar por False sin que se ignore
    if is_active is not None:
        web_types = web_types.filter(is_active=is_active)

    return [web_type_to_response(wt) for wt in web_types]


# ------------------------------------------------------------------------------
# GET /api/web-types/{id} — Detalle de un tipo de web
#
# Respuestas:
#   200 → datos del tipo de web con cantidad de clientes asignados
#   401 → token inválido
#   404 → tipo de web no encontrado
# ------------------------------------------------------------------------------
@router.get('/{web_type_id}', response_model=WebCatalogResponse)
def get_web_type(
    web_type_id: int,
    user: dict = Depends(get_current_user)
):
    try:
        web_type = WebCatalog.objects.get(id=web_type_id)
    except WebCatalog.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Tipo de web con id {web_type_id} no encontrado'
        )

    return web_type_to_response(web_type)


# ------------------------------------------------------------------------------
# POST /api/web-types/ — Crear tipo de web nuevo
#
# Solo Superadmin puede crear tipos de web.
# Verifica que el nombre no esté duplicado.
#
# Respuestas:
#   201 → tipo de web creado correctamente
#   400 → ya existe un tipo de web con ese nombre
#   401 → token inválido
#   403 → no es Superadmin
# ------------------------------------------------------------------------------
@router.post('/', response_model=WebCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_web_type(
    data: WebCatalogCreate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    # Verificar que no exista otro tipo de web con el mismo nombre
    if WebCatalog.objects.filter(name=data.name).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Ya existe un tipo de web con el nombre {data.name}'
        )

    web_type = WebCatalog.objects.create(
        name=data.name,
        base_price_rent=data.base_price_rent,
        base_price_sale=data.base_price_sale,
        is_active=data.is_active,
    )

    return web_type_to_response(web_type)


# ------------------------------------------------------------------------------
# PUT /api/web-types/{id} — Editar tipo de web existente
#
# Solo Superadmin puede editar tipos de web.
# Si viene un nuevo nombre verifica que no esté en uso por otro tipo.
#
# Respuestas:
#   200 → tipo de web actualizado
#   400 → nombre duplicado
#   401 → token inválido
#   403 → no es Superadmin
#   404 → tipo de web no encontrado
# ------------------------------------------------------------------------------
@router.put('/{web_type_id}', response_model=WebCatalogResponse)
def update_web_type(
    web_type_id: int,
    data: WebCatalogUpdate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        web_type = WebCatalog.objects.get(id=web_type_id)
    except WebCatalog.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Tipo de web con id {web_type_id} no encontrado'
        )

    update_data = data.model_dump(exclude_unset=True)

    # Si viene un nuevo nombre verificar que no esté en uso por otro tipo
    # exclude(id=web_type_id) → excluye el mismo registro
    if 'name' in update_data:
        if WebCatalog.objects.filter(name=update_data['name']).exclude(id=web_type_id).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Ya existe un tipo de web con el nombre {update_data["name"]}'
            )

    for field, value in update_data.items():
        setattr(web_type, field, value)

    web_type.save()

    return web_type_to_response(web_type)


# ------------------------------------------------------------------------------
# DELETE /api/web-types/{id} — Eliminar tipo de web
#
# Solo Superadmin puede eliminar tipos de web.
# No se puede eliminar si tiene clientes asignados —
# primero hay que reasignar esos clientes a otro tipo de web.
#
# Respuestas:
#   200 → tipo de web eliminado
#   400 → tiene clientes asignados
#   401 → token inválido
#   403 → no es Superadmin
#   404 → tipo de web no encontrado
# ------------------------------------------------------------------------------
@router.delete('/{web_type_id}')
def delete_web_type(
    web_type_id: int,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        web_type = WebCatalog.objects.get(id=web_type_id)
    except WebCatalog.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Tipo de web con id {web_type_id} no encontrado'
        )

    # Verificar que no tenga clientes asignados
    if web_type.clients.count() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'No se puede eliminar {web_type.name} porque tiene clientes asignados. Reasígnalos primero.'
        )

    web_type.delete()

    return {'message': f'Tipo de web {web_type.name} eliminado correctamente'}
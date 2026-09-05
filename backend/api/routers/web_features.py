# ==============================================================================
# ROUTERS/WEB_FEATURES.PY — Endpoints de funcionalidades adicionales
#
# Maneja todo lo relacionado a funcionalidades (/api/web-features/).
#
# Endpoints:
#   GET    /api/web-features/       → lista todas las funcionalidades
#   GET    /api/web-features/{id}   → detalle de una funcionalidad
#   POST   /api/web-features/       → crear funcionalidad nueva (solo Superadmin)
#   PUT    /api/web-features/{id}   → editar funcionalidad (solo Superadmin)
#   DELETE /api/web-features/{id}   → eliminar funcionalidad (solo Superadmin)
#
# Reglas de negocio:
#   - Solo Superadmin (L1) puede crear, editar y eliminar funcionalidades.
#   - No se puede eliminar una funcionalidad si tiene clientes asignados.
#   - Cualquier colaborador autenticado puede ver las funcionalidades.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional

from api.dependencies import get_current_user
from api.schemas.web_features import WebFeatureCreate, WebFeatureUpdate, WebFeatureResponse
from clients.models import WebFeature


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
# FUNCIÓN AUXILIAR — Convertir objeto Django WebFeature a dict
# ------------------------------------------------------------------------------
def feature_to_response(feature: WebFeature) -> dict:
    return {
        'id': feature.id,
        'name': feature.name,
        'extra_price': float(feature.extra_price),
        'is_active': feature.is_active,
        'created_at': feature.created_at,
    }


# ------------------------------------------------------------------------------
# GET /api/web-features/ — Listar todas las funcionalidades
#
# Soporta filtro por is_active: /api/web-features/?is_active=true
# Sin filtro → muestra todas.
#
# Respuestas:
#   200 → lista de funcionalidades
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/', response_model=list[WebFeatureResponse])
def get_web_features(
    is_active: Optional[bool] = None,  # None → muestra todas
    user: dict = Depends(get_current_user)
):
    features = WebFeature.objects.all()

    # is not None → permite filtrar por False sin que se ignore
    if is_active is not None:
        features = features.filter(is_active=is_active)

    return [feature_to_response(f) for f in features]


# ------------------------------------------------------------------------------
# GET /api/web-features/{id} — Detalle de una funcionalidad
#
# Respuestas:
#   200 → datos de la funcionalidad
#   401 → token inválido
#   404 → funcionalidad no encontrada
# ------------------------------------------------------------------------------
@router.get('/{feature_id}', response_model=WebFeatureResponse)
def get_web_feature(
    feature_id: int,
    user: dict = Depends(get_current_user)
):
    try:
        feature = WebFeature.objects.get(id=feature_id)
    except WebFeature.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Funcionalidad con id {feature_id} no encontrada'
        )

    return feature_to_response(feature)


# ------------------------------------------------------------------------------
# POST /api/web-features/ — Crear funcionalidad nueva
#
# Solo Superadmin puede crear funcionalidades.
# Verifica que el nombre no esté duplicado.
#
# Respuestas:
#   201 → funcionalidad creada correctamente
#   400 → ya existe una funcionalidad con ese nombre
#   401 → token inválido
#   403 → no es Superadmin
# ------------------------------------------------------------------------------
@router.post('/', response_model=WebFeatureResponse, status_code=status.HTTP_201_CREATED)
def create_web_feature(
    data: WebFeatureCreate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    # Verificar que no exista otra funcionalidad con el mismo nombre
    if WebFeature.objects.filter(name=data.name).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Ya existe una funcionalidad con el nombre {data.name}'
        )

    feature = WebFeature.objects.create(
        name=data.name,
        extra_price=data.extra_price,
        is_active=data.is_active,
    )

    return feature_to_response(feature)


# ------------------------------------------------------------------------------
# PUT /api/web-features/{id} — Editar funcionalidad existente
#
# Solo Superadmin puede editar funcionalidades.
# Si viene un nuevo nombre verifica que no esté en uso por otra.
#
# Respuestas:
#   200 → funcionalidad actualizada
#   400 → nombre duplicado
#   401 → token inválido
#   403 → no es Superadmin
#   404 → funcionalidad no encontrada
# ------------------------------------------------------------------------------
@router.put('/{feature_id}', response_model=WebFeatureResponse)
def update_web_feature(
    feature_id: int,
    data: WebFeatureUpdate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        feature = WebFeature.objects.get(id=feature_id)
    except WebFeature.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Funcionalidad con id {feature_id} no encontrada'
        )

    update_data = data.model_dump(exclude_unset=True)

    # Si viene un nuevo nombre verificar que no esté en uso por otra funcionalidad
    if 'name' in update_data:
        if WebFeature.objects.filter(name=update_data['name']).exclude(id=feature_id).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Ya existe una funcionalidad con el nombre {update_data["name"]}'
            )

    for field, value in update_data.items():
        setattr(feature, field, value)

    feature.save()

    return feature_to_response(feature)


# ------------------------------------------------------------------------------
# DELETE /api/web-features/{id} — Eliminar funcionalidad
#
# Solo Superadmin puede eliminar funcionalidades.
# No se puede eliminar si tiene clientes asignados —
# primero hay que quitar la funcionalidad de esos clientes.
#
# Respuestas:
#   200 → funcionalidad eliminada
#   400 → tiene clientes asignados
#   401 → token inválido
#   403 → no es Superadmin
#   404 → funcionalidad no encontrada
# ------------------------------------------------------------------------------
@router.delete('/{feature_id}')
def delete_web_feature(
    feature_id: int,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        feature = WebFeature.objects.get(id=feature_id)
    except WebFeature.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Funcionalidad con id {feature_id} no encontrada'
        )

    # Verificar que no tenga clientes asignados
    if feature.client_features.count() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'No se puede eliminar {feature.name} porque tiene clientes asignados. Quítala primero.'
        )

    feature.delete()

    return {'message': f'Funcionalidad {feature.name} eliminada correctamente'}
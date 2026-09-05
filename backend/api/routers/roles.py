# ==============================================================================
# ROUTERS/ROLES.PY — Endpoints de roles
#
# Maneja todo lo relacionado a roles (/api/roles/).
#
# Endpoints:
#   GET    /api/roles/       → lista todos los roles
#   GET    /api/roles/{id}   → detalle de un rol específico
#   POST   /api/roles/       → crear rol nuevo (solo Superadmin)
#   PUT    /api/roles/{id}   → editar rol existente (solo Superadmin)
#   DELETE /api/roles/{id}   → eliminar rol (solo Superadmin)
#
# Reglas de negocio:
#   - Solo Superadmin (L1) puede crear, editar y eliminar roles.
#   - No se puede eliminar el rol Superadmin (L1) nunca.
#   - No se puede eliminar un rol si tiene colaboradores asignados.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional

from api.dependencies import get_current_user
from api.schemas.roles import RoleCreate, RoleUpdate, RoleResponse
from clients.models import Role


router = APIRouter()


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Verificar que el usuario sea Superadmin (L1)
#
# Se llama en endpoints que solo puede usar el Superadmin.
# Recibe el dict que devuelve get_current_user con los datos del token.
# ------------------------------------------------------------------------------
def require_superadmin(user: dict):
    if user.get('role') != 'L1':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Solo el Superadmin puede realizar esta acción'
        )


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto Django Role a dict
# ------------------------------------------------------------------------------
def role_to_response(role: Role) -> dict:
    return {
        'id': role.id,
        'name': role.name,
        'level': role.level,
        # Contar cuántos colaboradores tienen este rol asignado
        'collaborators_count': role.collaborators.count(),
        'created_at': role.created_at,
    }


# ------------------------------------------------------------------------------
# GET /api/roles/ — Listar todos los roles
#
# Cualquier colaborador autenticado puede ver los roles.
# Se usa en el formulario de crear colaborador para el dropdown de roles.
#
# Respuestas:
#   200 → lista de roles ordenados por nivel (L1 primero)
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/', response_model=list[RoleResponse])
def get_roles(user: dict = Depends(get_current_user)):
    roles = Role.objects.all()
    return [role_to_response(r) for r in roles]


# ------------------------------------------------------------------------------
# GET /api/roles/{id} — Detalle de un rol
#
# Respuestas:
#   200 → datos del rol con cantidad de colaboradores asignados
#   401 → token inválido
#   404 → rol no encontrado
# ------------------------------------------------------------------------------
@router.get('/{role_id}', response_model=RoleResponse)
def get_role(
    role_id: int,
    user: dict = Depends(get_current_user)
):
    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Rol con id {role_id} no encontrado'
        )

    return role_to_response(role)


# ------------------------------------------------------------------------------
# POST /api/roles/ — Crear rol nuevo
#
# Solo Superadmin puede crear roles.
# Verifica que el nombre y nivel no estén duplicados.
#
# Respuestas:
#   201 → rol creado correctamente
#   400 → ya existe un rol con ese nombre o nivel
#   401 → token inválido
#   403 → no es Superadmin
# ------------------------------------------------------------------------------
@router.post('/', response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    if Role.objects.filter(name=data.name).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Ya existe un rol con el nombre {data.name}'
        )

    if Role.objects.filter(level=data.level).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Ya existe un rol con el nivel {data.level}'
        )

    role = Role.objects.create(
        name=data.name,
        level=data.level
    )

    return role_to_response(role)


# ------------------------------------------------------------------------------
# PUT /api/roles/{id} — Editar rol existente
#
# Solo Superadmin puede editar roles.
# model_dump(exclude_unset=True) → solo actualiza los campos enviados.
#
# Respuestas:
#   200 → rol actualizado
#   401 → token inválido
#   403 → no es Superadmin
#   404 → rol no encontrado
# ------------------------------------------------------------------------------
@router.put('/{role_id}', response_model=RoleResponse)
def update_role(
    role_id: int,
    data: RoleUpdate,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Rol con id {role_id} no encontrado'
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(role, field, value)

    role.save()

    return role_to_response(role)


# ------------------------------------------------------------------------------
# DELETE /api/roles/{id} — Eliminar rol
#
# Solo Superadmin puede eliminar roles.
# No se puede eliminar si tiene colaboradores asignados.
# No se puede eliminar el rol Superadmin (L1) nunca —
# el sistema siempre debe tener al menos un Superadmin activo.
#
# Respuestas:
#   200 → rol eliminado
#   400 → tiene colaboradores asignados o es el rol Superadmin
#   401 → token inválido
#   403 → no es Superadmin
#   404 → rol no encontrado
# ------------------------------------------------------------------------------
@router.delete('/{role_id}')
def delete_role(
    role_id: int,
    user: dict = Depends(get_current_user)
):
    require_superadmin(user)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Rol con id {role_id} no encontrado'
        )

    # Verificar que no tenga colaboradores asignados
    if role.collaborators.count() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'No se puede eliminar el rol {role.name} porque tiene colaboradores asignados'
        )

    # Verificar que no sea el rol Superadmin (L1)
    # El sistema siempre debe tener al menos un Superadmin activo
    if role.level == 'L1':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No se puede eliminar el rol Superadmin. El sistema siempre debe tener un L1.'
        )

    role.delete()

    return {'message': f'Rol {role.name} eliminado correctamente'}
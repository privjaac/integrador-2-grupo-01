# ==============================================================================
# ROUTERS/ROLES.PY — Endpoints de roles
#
# Maneja todo lo relacionado a roles (/api/roles/).
#
# Endpoints:
#   GET    /api/roles/       → lista todos los roles
#   GET    /api/roles/{id}   → detalle de un rol específico
#   PUT    /api/roles/{id}   → editar rol existente (solo Superadmin)
#
# Reglas de negocio:
#   - Los cinco niveles son fijos; solo Superadmin edita nombre y descripción.
# ==============================================================================

from fastapi import HTTPException, status, Depends
from api.router import APIRouter

from api.dependencies import get_current_user
from api.schemas.roles import RoleUpdate, RoleResponse
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
    hierarchy = int(role.level[1:])
    return {
        'id': role.id,
        'name': role.name,
        'level': role.level,
        'hierarchy': hierarchy,
        'can_create_users': hierarchy < 5,
        'min_role_create': hierarchy + 1 if hierarchy < 5 else None,
        'description': role.description,
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

    if role.level == 'L1':
        raise HTTPException(status_code=403, detail='El rol Superadmin está protegido')
    if 'name' in update_data and Role.objects.filter(name=update_data['name']).exclude(id=role_id).exists():
        raise HTTPException(status_code=400, detail='Ya existe un rol con ese nombre')

    for field, value in update_data.items():
        setattr(role, field, value)

    role.save()

    return role_to_response(role)

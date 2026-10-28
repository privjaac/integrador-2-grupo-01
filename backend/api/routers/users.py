# ==============================================================================
# ROUTERS/USERS.PY — Endpoints de colaboradores
#
# Maneja todo lo relacionado a colaboradores (/api/users/).
#
# Endpoints:
#   GET    /api/users/       → lista todos los colaboradores
#   GET    /api/users/{id}   → detalle de un colaborador específico
#   POST   /api/users/       → crear colaborador nuevo (L1 a L4)
#   PUT    /api/users/{id}   → editar colaborador existente
#   DELETE /api/users/{id}   → dar de baja un colaborador
#
# Reglas de negocio:
#   - Solo L1 a L4 pueden crear colaboradores. L5 no puede.
#   - No se puede dar de baja al único Superadmin activo.
#   - La contraseña nunca se devuelve en ninguna respuesta.
#   - El CUPE se genera automáticamente al crear.
# ==============================================================================

from fastapi import HTTPException, status, Depends
from api.router import APIRouter
from django.db import IntegrityError, transaction
from typing import Optional
from django.db.models import Q

# Depends(get_current_user) → FastAPI verifica el token automáticamente
# antes de ejecutar cada endpoint. Si el token es inválido → 401.
from api.dependencies import get_current_user
from api.routers.auth import hash_password
from api.role_permissions import effective_permissions
from api.schemas.users import CollaboratorCreate, CollaboratorUpdate, CollaboratorResponse, CollaboratorList
from clients.models import Collaborator, Role


router = APIRouter()


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Verificar que el usuario puede crear colaboradores
#
# Solo L1, L2, L3 y L4 pueden crear colaboradores.
# L5 (Developer) no tiene ese permiso.
# Se llama después de get_current_user que ya verificó el token.
# ------------------------------------------------------------------------------
def require_can_create_users(user: dict):
    role = user.get('role')
    if role not in ['L1', 'L2', 'L3', 'L4']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No tienes permiso para crear colaboradores'
        )


def require_can_view_users(user: dict):
    if user.get('role') not in ('L1', 'L2', 'L3', 'L4'):
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar colaboradores')


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
# FUNCIÓN AUXILIAR — Generar CUPE para colaborador
#
# Formato: ELO-00000000 (ELO + 8 dígitos)
# Usa hash lineal para que el código no sea predecible.
# Fórmula: (id * 7919 + 999999) % 100000000
# Ejemplo: id=1 → ELO-01007918, id=2 → ELO-01015837
# Nunca se repite porque 7919 es número primo.
# El id=0 (ELO-00000000) está reservado para el Superadmin base.
# ------------------------------------------------------------------------------
def generate_cupe(id: int) -> str:
    code = (id * 7919 + 999999) % 100000000
    return f"ELO-{str(code).zfill(8)}"


# ------------------------------------------------------------------------------
# FUNCIÓN AUXILIAR — Convertir objeto Django Collaborator a dict
#
# FastAPI no puede leer directamente un objeto Django — necesita un dict.
# Esta función hace esa conversión campo por campo.
# Nunca incluye password_hash — jamás se manda al frontend.
# ------------------------------------------------------------------------------
def collaborator_to_response(collaborator: Collaborator) -> dict:
    return {
        'id': collaborator.id,
        'cupe': collaborator.cupe,
        'first_name': collaborator.first_name,
        'last_name': collaborator.last_name,
        'document_type': collaborator.document_type,
        'document_number': collaborator.document_number,
        'email': collaborator.email,
        'phone': collaborator.phone,
        'city': collaborator.city,
        'username': collaborator.username,
        # Nunca incluimos password_hash — jamás se manda al frontend
        'role_id': collaborator.role_id,
        'role_name': collaborator.role.name if collaborator.role else None,
        'role_level': collaborator.role.level if collaborator.role else None,
        'role': collaborator.role.level if collaborator.role else None,
        'role_active': collaborator.role.is_active if collaborator.role else False,
        'permissions': effective_permissions(collaborator.role),
        'area': collaborator.area,
        'work_area': collaborator.area,
        'is_active': collaborator.is_active,
        'created_at': collaborator.created_at,
        'updated_at': collaborator.updated_at,
    }


# ------------------------------------------------------------------------------
# GET /api/users/ — Listar todos los colaboradores
#
# Cualquier colaborador autenticado puede ver la lista.
# Soporta filtro por is_active: /api/users/?is_active=true o false
# Sin filtro → muestra todos (activos e inactivos)
#
# Respuestas:
#   200 → lista de colaboradores
#   401 → token inválido
# ------------------------------------------------------------------------------
@router.get('/me', response_model=CollaboratorResponse)
def get_me(user: dict = Depends(get_current_user)):
    collaborator = Collaborator.objects.select_related('role').get(
        id=user['collaborator_id']
    )
    return collaborator_to_response(collaborator)


@router.get('/', response_model=list[CollaboratorResponse])
def get_collaborators(
    is_active: Optional[bool] = None,  # None → muestra todos sin filtrar
    role_id: Optional[int] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    require_can_view_users(user)
    # select_related('role') precarga el rol de cada colaborador
    # para no hacer una consulta extra por cada uno (optimización)
    collaborators = Collaborator.objects.select_related('role').all()

    # is not None → permite filtrar por False (inactivos) sin que se ignore
    # Si usáramos solo "if is_active" → filtrar por False nunca entraría al bloque
    if is_active is not None:
        collaborators = collaborators.filter(is_active=is_active)
    if role_id is not None:
        collaborators = collaborators.filter(role_id=role_id)
    if search:
        collaborators = collaborators.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search)
            | Q(username__icontains=search) | Q(email__icontains=search)
            | Q(cupe__icontains=search) | Q(document_number__icontains=search)
        )

    return [collaborator_to_response(c) for c in collaborators]


def require_lower_role(user: dict, role: Role, *, allow_l1_creation: bool = False):
    current_level = int(user['role'][1:])
    target_level = int(role.level[1:])
    l1_creation = allow_l1_creation and current_level == 1 and target_level == 1
    if target_level <= 1 and not l1_creation or target_level <= current_level and not l1_creation:
        raise HTTPException(
            status_code=403,
            detail='Solo puedes gestionar colaboradores de menor jerarquía',
        )


def require_manage_target(user: dict, collaborator: Collaborator):
    """Verifica competencia y alcance ordinario de edición/estado."""
    if user.get('role') not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='Solo SA/SM pueden administrar colaboradores')
    if collaborator.id == user.get('collaborator_id'):
        raise HTTPException(status_code=403, detail='No puedes administrar tu propia cuenta por esta operación')
    if not collaborator.role or collaborator.role.level not in {'L1', 'L2', 'L3', 'L4', 'L5'}:
        raise HTTPException(status_code=403, detail='El nivel del colaborador objetivo no es válido')
    if collaborator.role.level == 'L1':
        raise HTTPException(status_code=403, detail='No se permite administrar otra cuenta L1')

# ------------------------------------------------------------------------------
# GET /api/users/{id} — Detalle de un colaborador
#
# Respuestas:
#   200 → datos completos del colaborador (sin contraseña)
#   401 → token inválido
#   404 → colaborador no encontrado
# ------------------------------------------------------------------------------
@router.get('/{collaborator_id}', response_model=CollaboratorResponse)
def get_collaborator(
    collaborator_id: int,
    user: dict = Depends(get_current_user)
):
    require_can_view_users(user)
    try:
        collaborator = Collaborator.objects.select_related('role').get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Colaborador con id {collaborator_id} no encontrado'
        )

    return collaborator_to_response(collaborator)


# ------------------------------------------------------------------------------
# POST /api/users/ — Crear colaborador nuevo
#
# Solo L1 a L4 pueden crear colaboradores.
# La contraseña se encripta con bcrypt antes de guardar.
# El CUPE se genera automáticamente con el ID asignado por Django.
#
# Respuestas:
#   201 → colaborador creado con CUPE asignado
#   400 → username, email o documento ya existen
#   401 → token inválido
#   403 → no tiene permiso (es L5)
# ------------------------------------------------------------------------------
@router.post('/', response_model=CollaboratorResponse, status_code=status.HTTP_201_CREATED)
def create_collaborator(
    data: CollaboratorCreate,
    user: dict = Depends(get_current_user)
):
    # Verificar que tenga permiso para crear colaboradores
    require_can_create_users(user)

    # Verificar que el username no esté en uso
    if Collaborator.objects.filter(username=data.username).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'El username {data.username} ya está en uso'
        )

    # Verificar que el email no esté en uso
    if Collaborator.objects.filter(email=data.email).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'El email {data.email} ya está registrado'
        )

    # Verificar que el número de documento no esté en uso
    if Collaborator.objects.filter(document_number=data.document_number).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'El documento {data.document_number} ya está registrado'
        )

    # Crear el colaborador con la contraseña encriptada
    # hash_password convierte la contraseña en texto plano a bcrypt
    # Nunca guardamos la contraseña original — solo el hash
    try:
        with transaction.atomic():
            # Serialize account creation with role deactivation/deletion so a
            # role cannot become inactive between validation and assignment.
            role = Role.objects.select_for_update().filter(
                id=data.role_id, is_active=True,
            ).first()
            if role is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Rol con id {data.role_id} no encontrado'
                )
            require_lower_role(user, role, allow_l1_creation=True)
            collaborator = Collaborator.objects.create(
                first_name=data.first_name,
                last_name=data.last_name,
                document_type=data.document_type,
                document_number=data.document_number,
                email=data.email,
                phone=data.phone,
                city=data.city,
                username=data.username,
                password_hash=hash_password(data.password),
                role=role,
                area=data.area,
                is_active=True,
            )
            collaborator.cupe = generate_cupe(collaborator.id)
            collaborator.save()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=400,
            detail='El username, email, documento o CUPE ya está registrado',
        ) from exc

    return collaborator_to_response(collaborator)


# ------------------------------------------------------------------------------
# PUT /api/users/{id} — Editar colaborador existente
#
# Cualquier L1 a L4 puede editar colaboradores.
# Si se manda una nueva contraseña, se encripta antes de guardar.
# Si no se manda contraseña, la actual no se toca.
# model_dump(exclude_unset=True) → solo actualiza los campos enviados.
#
# Respuestas:
#   200 → colaborador actualizado
#   401 → token inválido
#   403 → no tiene permiso
#   404 → colaborador no encontrado
# ------------------------------------------------------------------------------
@router.put('/{collaborator_id}', response_model=CollaboratorResponse)
def update_collaborator(
    collaborator_id: int,
    data: CollaboratorUpdate,
    user: dict = Depends(get_current_user)
):
    if user.get('role') not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='Solo SA/SM pueden editar colaboradores')

    try:
        collaborator = Collaborator.objects.select_related('role').get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Colaborador con id {collaborator_id} no encontrado'
        )
    require_manage_target(user, collaborator)

    update_data = data.model_dump(exclude_unset=True)
    if 'role_id' in update_data:
        raise HTTPException(status_code=403, detail='El cambio de rol no está disponible en la edición ordinaria')
    unique_fields = {
        'username': 'El username ya está en uso',
        'email': 'El email ya está registrado',
        'document_number': 'El documento ya está registrado',
    }
    for field, message in unique_fields.items():
        if (
            field in update_data
            and Collaborator.objects.filter(**{field: update_data[field]})
            .exclude(id=collaborator_id).exists()
        ):
            raise HTTPException(status_code=400, detail=message)
    if 'is_active' in update_data:
        if update_data != {'is_active': True}:
            raise HTTPException(status_code=403, detail='Usa la operación autorizada de activación/desactivación')
        collaborator.is_active = True
        collaborator.save(update_fields=['is_active', 'updated_at'])
        return collaborator_to_response(collaborator)

    for field, value in update_data.items():

        # Si viene una nueva contraseña, encriptarla antes de guardar
        if field == 'password':
            collaborator.password_hash = hash_password(value)

        # Si viene un nuevo rol, buscar el objeto Role
        elif field == 'role_id':
            try:
                role = Role.objects.get(id=value, is_active=True)
            except Role.DoesNotExist:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Rol con id {value} no encontrado'
                )
            require_lower_role(user, role)
            collaborator.role = role

        else:
            setattr(collaborator, field, value)

    try:
        collaborator.save()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=400,
            detail='El username, email, documento o CUPE ya está registrado',
        ) from exc

    return collaborator_to_response(collaborator)


# ------------------------------------------------------------------------------
# DELETE /api/users/{id} — Dar de baja un colaborador
#
# No elimina el registro — solo cambia is_active a False (soft delete).
# Así se conserva el historial completo.
#
# Regla crítica: no se puede dar de baja al único Superadmin activo.
# El sistema siempre debe tener al menos un Superadmin funcionando.
#
# Solo Superadmin puede dar de baja colaboradores.
#
# Respuestas:
#   200 → colaborador dado de baja
#   400 → es el único Superadmin activo
#   401 → token inválido
#   403 → no es Superadmin
#   404 → colaborador no encontrado
# ------------------------------------------------------------------------------
@router.delete('/{collaborator_id}')
def delete_collaborator(
    collaborator_id: int,
    user: dict = Depends(get_current_user)
):
    if user.get('role') not in ('L1', 'L2'):
        raise HTTPException(status_code=403, detail='Solo SA/SM pueden cambiar el estado de colaboradores')

    try:
        collaborator = Collaborator.objects.select_related('role').get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Colaborador con id {collaborator_id} no encontrado'
        )

    require_manage_target(user, collaborator)

    # Soft delete — conserva historial; el nivel L1 objetivo está protegido.
    collaborator.is_active = False
    collaborator.save()

    return {'message': f'Colaborador {collaborator.cupe} dado de baja correctamente'}

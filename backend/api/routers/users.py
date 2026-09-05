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

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional

# Depends(get_current_user) → FastAPI verifica el token automáticamente
# antes de ejecutar cada endpoint. Si el token es inválido → 401.
from api.dependencies import get_current_user
from api.routers.auth import hash_password
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
        'area': collaborator.area,
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
@router.get('/', response_model=list[CollaboratorList])
def get_collaborators(
    is_active: Optional[bool] = None,  # None → muestra todos sin filtrar
    user: dict = Depends(get_current_user)
):
    # select_related('role') precarga el rol de cada colaborador
    # para no hacer una consulta extra por cada uno (optimización)
    collaborators = Collaborator.objects.select_related('role').all()

    # is not None → permite filtrar por False (inactivos) sin que se ignore
    # Si usáramos solo "if is_active" → filtrar por False nunca entraría al bloque
    if is_active is not None:
        collaborators = collaborators.filter(is_active=is_active)

    return [
        {
            'id': c.id,
            'cupe': c.cupe,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'role_name': c.role.name if c.role else None,
            'city': c.city,
            'is_active': c.is_active,
        }
        for c in collaborators
    ]


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

    # Verificar que el rol exista
    try:
        role = Role.objects.get(id=data.role_id)
    except Role.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Rol con id {data.role_id} no encontrado'
        )

    # Crear el colaborador con la contraseña encriptada
    # hash_password convierte la contraseña en texto plano a bcrypt
    # Nunca guardamos la contraseña original — solo el hash
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
        is_active=True,  # Todo colaborador nuevo empieza activo
    )

    # Generar CUPE usando el ID que Django asignó automáticamente
    collaborator.cupe = generate_cupe(collaborator.id)
    collaborator.save()

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
    require_can_create_users(user)

    try:
        collaborator = Collaborator.objects.select_related('role').get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Colaborador con id {collaborator_id} no encontrado'
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():

        # Si viene una nueva contraseña, encriptarla antes de guardar
        if field == 'password':
            collaborator.password_hash = hash_password(value)

        # Si viene un nuevo rol, buscar el objeto Role
        elif field == 'role_id':
            try:
                collaborator.role = Role.objects.get(id=value)
            except Role.DoesNotExist:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Rol con id {value} no encontrado'
                )

        else:
            setattr(collaborator, field, value)

    collaborator.save()

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
    # Solo Superadmin puede dar de baja colaboradores
    require_superadmin(user)

    try:
        collaborator = Collaborator.objects.select_related('role').get(id=collaborator_id)
    except Collaborator.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Colaborador con id {collaborator_id} no encontrado'
        )

    # Verificar que no sea el único Superadmin activo
    if collaborator.role and collaborator.role.level == 'L1':
        superadmins_activos = Collaborator.objects.filter(
            role__level='L1',
            is_active=True
        ).count()

        if superadmins_activos <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='No se puede dar de baja al único Superadmin activo. Asigna otro Superadmin primero.'
            )

    # Soft delete — no borramos, solo desactivamos
    collaborator.is_active = False
    collaborator.save()

    return {'message': f'Colaborador {collaborator.cupe} dado de baja correctamente'}
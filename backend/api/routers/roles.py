"""Organizational role administration within the fixed L1-L5 ceilings."""
from fastapi import Depends, HTTPException, status
from django.db import IntegrityError, transaction

from api.dependencies import get_current_user
from api.role_permissions import CAPABILITY_LEVELS, effective_permissions, valid_permissions
from api.router import APIRouter
from api.schemas.roles import RoleCreate, RoleResponse, RoleUpdate
from clients.models import Collaborator, Role, RoleHistory

router = APIRouter()


def require_superadmin(user: dict):
    if user.get('role') != 'L1':
        raise HTTPException(status_code=403, detail='Solo el Superadmin puede administrar roles')


def actor_for(user: dict) -> Collaborator:
    actor = Collaborator.objects.select_related('role').filter(
        pk=user.get('collaborator_id'), is_active=True, role__level='L1', role__is_active=True,
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='La cuenta Superadmin no está activa')
    return actor


def role_snapshot(role: Role) -> dict:
    return {
        'name': role.name, 'level': role.level, 'description': role.description,
        'is_active': role.is_active, 'permissions': effective_permissions(role),
    }


def record_history(role: Role, actor: Collaborator, action: str, before=None, after=None):
    RoleHistory.objects.create(
        role=role, role_id_snapshot=role.pk, role_name_snapshot=role.name,
        actor=actor, action=action, before_data=before, after_data=after,
    )


def role_to_response(role: Role) -> dict:
    hierarchy = int(role.level[1:])
    return {
        'id': role.id, 'name': role.name, 'level': role.level,
        'hierarchy': hierarchy, 'can_create_users': hierarchy < 5,
        'min_role_create': hierarchy + 1 if hierarchy < 5 else None,
        'description': role.description, 'is_active': role.is_active,
        'permissions': effective_permissions(role),
        'permissions_editable': not (role.level == 'L1' and role.permissions is None),
        'collaborators_count': role.collaborators.count(), 'created_at': role.created_at,
    }


@router.get('/', response_model=list[RoleResponse])
def get_roles(user: dict = Depends(get_current_user)):
    return [role_to_response(role) for role in Role.objects.all()]


@router.get('/permission-catalog')
def get_permission_catalog(user: dict = Depends(get_current_user)):
    return [{'key': key, 'levels': sorted(levels)} for key, levels in sorted(CAPABILITY_LEVELS.items())]


@router.get('/history')
def get_role_history(user: dict = Depends(get_current_user)):
    require_superadmin(user)
    return list(RoleHistory.objects.order_by('-recorded_at', '-id').values(
        'id', 'role_id_snapshot', 'role_name_snapshot', 'actor_id', 'action',
        'before_data', 'after_data', 'recorded_at',
    )[:500])


@router.get('/{role_id}', response_model=RoleResponse)
def get_role(role_id: int, user: dict = Depends(get_current_user)):
    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise HTTPException(status_code=404, detail=f'Rol con id {role_id} no encontrado')
    return role_to_response(role)


@router.post('/', response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(data: RoleCreate, user: dict = Depends(get_current_user)):
    require_superadmin(user)
    actor = actor_for(user)
    name = data.name.strip()
    if not valid_permissions(data.level, data.permissions):
        raise HTTPException(status_code=422, detail='Permiso inválido o fuera del nivel asignado')
    if Role.objects.filter(name__iexact=name).exists():
        raise HTTPException(status_code=409, detail='El rol ya existe')
    try:
        with transaction.atomic():
            role = Role.objects.create(
                name=name, level=data.level, description=data.description.strip(),
                permissions=data.permissions, is_active=data.is_active,
            )
            record_history(role, actor, 'created', after=role_snapshot(role))
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='El rol ya existe') from exc
    return role_to_response(role)


@router.put('/{role_id}', response_model=RoleResponse)
def update_role(role_id: int, data: RoleUpdate, user: dict = Depends(get_current_user)):
    require_superadmin(user)
    actor = actor_for(user)
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail='Indica al menos un cambio')
    if 'name' in updates:
        updates['name'] = updates['name'].strip()
    with transaction.atomic():
        role = Role.objects.select_for_update().filter(pk=role_id).first()
        if role is None:
            raise HTTPException(status_code=404, detail='Rol no encontrado')
        before = role_snapshot(role)
        if 'permissions' in updates and not valid_permissions(role.level, updates['permissions']):
            raise HTTPException(status_code=422, detail='Permiso inválido o fuera del nivel asignado')
        if 'name' in updates and Role.objects.filter(name__iexact=updates['name']).exclude(pk=role.pk).exists():
            raise HTTPException(status_code=409, detail='El rol ya existe')
        effective_change = 'permissions' in updates or ('is_active' in updates and updates['is_active'] != role.is_active)
        other_active_l1 = role.collaborators.filter(is_active=True, role__level='L1').exclude(pk=actor.pk).exists()
        if effective_change and other_active_l1:
            raise HTTPException(status_code=403, detail='No puedes cambiar los permisos efectivos de otra cuenta L1')
        if role.level == 'L1' and updates.get('is_active') is False:
            raise HTTPException(status_code=409, detail='No se puede desactivar un rol de nivel L1')
        if role.level == 'L1' and 'permissions' in updates and role.permissions is None:
            # Keep the established Superadmin baseline from being reduced by
            # reconfiguring the role assigned to all current L1 accounts.
            raise HTTPException(status_code=409, detail='El conjunto del rol L1 existente está protegido')
        for field, value in updates.items():
            setattr(role, field, value)
        try:
            role.save()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail='El rol ya existe') from exc
        after = role_snapshot(role)
        action = 'deactivated' if before['is_active'] and not role.is_active else 'updated'
        record_history(role, actor, action, before=before, after=after)
    return role_to_response(role)


@router.delete('/{role_id}')
def delete_role(role_id: int, user: dict = Depends(get_current_user)):
    require_superadmin(user)
    actor = actor_for(user)
    with transaction.atomic():
        role = Role.objects.select_for_update().filter(pk=role_id).first()
        if role is None:
            raise HTTPException(status_code=404, detail='Rol no encontrado')
        if role.level == 'L1':
            raise HTTPException(status_code=409, detail='No se puede eliminar un rol de nivel L1')
        if role.collaborators.filter(is_active=True).exists():
            raise HTTPException(status_code=409, detail='No se puede eliminar un rol asignado a colaboradores activos')
        if role.collaborators.exists():
            raise HTTPException(status_code=409, detail='Desactiva o reasigna las cuentas inactivas antes de eliminar el rol')
        before = role_snapshot(role)
        record_history(role, actor, 'deleted', before=before)
        role.delete()
    return {'message': 'Rol eliminado; su historial se conserva.'}

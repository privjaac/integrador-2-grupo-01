from fastapi import Depends, HTTPException, status
from django.db import IntegrityError, transaction

from api.dependencies import get_current_user, require_user_permission
from api.router import APIRouter
from api.schemas.elomux_platforms import (
    ElomuxPlatformCreate, ElomuxPlatformResponse, ElomuxPlatformUpdate,
)
from clients.models import Collaborator, ElomuxPlatform, ElomuxPlatformEvent


router = APIRouter()


def platform_snapshot(platform: ElomuxPlatform) -> dict:
    return {'name': platform.name, 'url': platform.url, 'is_active': platform.is_active}


def platform_response(platform: ElomuxPlatform) -> dict:
    return {
        'id': platform.id, 'name': platform.name, 'url': platform.url,
        'is_active': platform.is_active, 'created_at': platform.created_at,
        'updated_at': platform.updated_at,
    }


def require_platform_manager(user: dict) -> Collaborator:
    require_user_permission(user, 'platforms', 'manage')
    actor = Collaborator.objects.filter(
        pk=user.get('collaborator_id'), is_active=True, role__is_active=True,
        role__level__in=('L1', 'L2'),
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='Solo SA o SM pueden gestionar plataformas ELOMUX')
    return actor


@router.get('/', response_model=list[ElomuxPlatformResponse])
def list_elomux_platforms(user: dict = Depends(get_current_user)):
    require_user_permission(user, 'platforms', 'view')
    return [platform_response(item) for item in ElomuxPlatform.objects.all()]


@router.post('/', response_model=ElomuxPlatformResponse, status_code=status.HTTP_201_CREATED)
def create_elomux_platform(data: ElomuxPlatformCreate, user: dict = Depends(get_current_user)):
    actor = require_platform_manager(user)
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail='El nombre de la plataforma es obligatorio')
    url = str(data.url)
    try:
        with transaction.atomic():
            if ElomuxPlatform.objects.filter(name__iexact=name).exists():
                raise HTTPException(status_code=409, detail='Esta plataforma ya se encuentra registrada')
            platform = ElomuxPlatform.objects.create(
                name=name, url=url, is_active=data.is_active,
                created_by=actor, updated_by=actor,
            )
            ElomuxPlatformEvent.objects.create(
                platform=platform, actor=actor, action='created',
                after=platform_snapshot(platform),
            )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='Esta plataforma ya se encuentra registrada') from exc
    return platform_response(platform)


@router.put('/{platform_id}', response_model=ElomuxPlatformResponse)
def update_elomux_platform(
    platform_id: int, data: ElomuxPlatformUpdate, user: dict = Depends(get_current_user),
):
    actor = require_platform_manager(user)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail='Indica al menos un dato para actualizar')
    if 'name' in changes:
        changes['name'] = changes['name'].strip()
        if not changes['name']:
            raise HTTPException(status_code=422, detail='El nombre de la plataforma es obligatorio')
    if 'url' in changes:
        changes['url'] = str(changes['url'])

    try:
        with transaction.atomic():
            platform = ElomuxPlatform.objects.select_for_update().filter(pk=platform_id).first()
            if platform is None:
                raise HTTPException(status_code=404, detail='Plataforma ELOMUX no encontrada')
            if 'name' in changes and ElomuxPlatform.objects.filter(
                name__iexact=changes['name'],
            ).exclude(pk=platform_id).exists():
                raise HTTPException(status_code=409, detail='Esta plataforma ya se encuentra registrada')

            before = platform_snapshot(platform)
            for field, value in changes.items():
                setattr(platform, field, value)
            platform.updated_by = actor
            platform.save(update_fields=[*changes.keys(), 'updated_by', 'updated_at'])
            ElomuxPlatformEvent.objects.create(
                platform=platform, actor=actor, action='updated',
                before=before, after=platform_snapshot(platform),
            )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='Esta plataforma ya se encuentra registrada') from exc
    return platform_response(platform)\n

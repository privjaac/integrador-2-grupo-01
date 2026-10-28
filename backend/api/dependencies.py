# ==============================================================================
# DEPENDENCIES.PY — Dependencias compartidas de FastAPI
#
# FastAPI tiene un sistema de "dependencias" que permite reutilizar
# funciones comunes en múltiples endpoints.
#
# Aquí definimos get_current_user usando HTTPBearer — esto hace que
# /docs muestre el botón Authorize correctamente y maneje el token
# de forma estándar en todos los endpoints.
# ==============================================================================

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from django.db import connections
from api.routers.auth import decode_token
from clients.models import Collaborator
from clients.models import CollaboratorSession
from django.utils import timezone
from api.role_permissions import effective_permissions, permission_for_route

# HTTPBearer lee automáticamente el header Authorization: Bearer <token>
# y extrae el token — no hay que hacerlo manualmente
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Dependencia que verifica el token en cada endpoint protegido.
    FastAPI la llama automáticamente antes de ejecutar el endpoint.
    Si el token es inválido o no viene → lanza error 401 automáticamente.
    Devuelve el contenido del token (username, rol, collaborator_id).
    """
    payload = decode_token(credentials.credentials)
    if payload.get('type') != 'access':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Se requiere un token de acceso',
        )

    try:
        collaborator_id = int(payload.get('collaborator_id'))
    except (TypeError, ValueError):
        collaborator_id = None
    session_id = payload.get('sid')

    try:
        if not session_id or not CollaboratorSession.objects.filter(
            id=session_id, collaborator_id=collaborator_id, revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            raise HTTPException(status_code=401, detail='Sesión inválida o revocada')
        collaborator = Collaborator.objects.select_related('role').filter(
            id=collaborator_id,
            username=payload.get('sub'),
            is_active=True,
            role__is_active=True,
        ).first()
    finally:
        connections.close_all()
    if collaborator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Usuario no encontrado o inactivo',
        )

    return {
        **payload,
        'collaborator_id': collaborator.id,
        'role': collaborator.role.level if collaborator.role else None,
        'role_id': collaborator.role_id,
        'permissions': effective_permissions(collaborator.role),
    }


def require_route_permission(request: Request, user: dict = Depends(get_current_user)) -> None:
    """Apply the configured role subset before each protected API operation."""
    route_name = getattr(request.scope.get('route'), 'name', None)
    # A collaborator may always retrieve their own identity after login.
    if route_name in {'get_me', 'resolve_client_request'}:
        return
    # The inbox is not protected by a broad module permission: its handlers
    # return only notifications in the caller's own current scope.
    if route_name in {'list_internal_notifications', 'mark_internal_notification_read'}:
        return
    if route_name == 'get_task_context':
        if any(permission.startswith('tasks.') for permission in user.get('permissions', [])):
            return
        raise HTTPException(status_code=403, detail='El rol organizacional no tiene este permiso')
    permission = permission_for_route(route_name)
    if permission is None:
        raise HTTPException(status_code=403, detail='El rol organizacional no tiene este permiso')
    require_user_permission(user, *permission.rsplit('.', 1))


def require_user_permission(user: dict, module: str, action: str) -> None:
    if f'{module}.{action}' not in user.get('permissions', []):
        raise HTTPException(status_code=403, detail='El rol organizacional no tiene este permiso')

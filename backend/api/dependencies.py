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

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from django.db import connections
from api.routers.auth import decode_token
from clients.models import Collaborator

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

    try:
        collaborator = Collaborator.objects.select_related('role').filter(
            id=collaborator_id,
            username=payload.get('sub'),
            is_active=True,
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
    }

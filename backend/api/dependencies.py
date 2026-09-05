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
from api.routers.auth import decode_token

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
    return decode_token(credentials.credentials)
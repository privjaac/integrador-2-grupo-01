# ==============================================================================
# SCHEMAS/AUTH.PY — Schemas de autenticación
#
# Define la forma de los datos que entran y salen en el login.
#
# Hay 3 schemas aquí:
#   - LoginRequest  → lo que React manda al hacer login
#   - TokenResponse → lo que el backend responde con los tokens
#   - RefreshRequest → lo que React manda para renovar el token
# ==============================================================================

from typing import Optional
from pydantic import BaseModel


# ------------------------------------------------------------------------------
# LOGINREQUEST — Datos que llegan cuando el usuario hace login
#
# React manda un JSON así:
# {
#   "username": "piter",
#   "password": "mi-contraseña"
# }
# ------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: int
    cupe: Optional[str]
    username: str
    first_name: str
    last_name: str
    email: str
    role: Optional[str]
    role_name: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# TOKENRESPONSE — Lo que el backend responde después del login exitoso
#
# FastAPI devuelve un JSON así:
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",
#   "token_type": "bearer"
# }
#
# React guarda estos tokens y los manda en cada petición siguiente.
# ------------------------------------------------------------------------------
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    user: Optional[AuthUser] = None


# ------------------------------------------------------------------------------
# REFRESHREQUEST — Datos que llegan cuando React quiere renovar el token
#
# Cuando el access_token vence (30 min), React manda el refresh_token
# para obtener uno nuevo sin pedirle al usuario que vuelva a hacer login.
#
# React manda un JSON así:
# {
#   "refresh_token": "eyJ..."
# }
# ------------------------------------------------------------------------------
class RefreshRequest(BaseModel):
    refresh_token: str
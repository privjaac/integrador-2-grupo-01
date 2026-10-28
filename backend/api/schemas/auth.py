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

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
    username: str   # Nombre de usuario
    password: str   # Contraseña en texto plano (FastAPI la compara con el hash)


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
    access_token: str    # Token de corta duración (30 min) — para hacer peticiones
    refresh_token: str   # Token de larga duración (24h) — para renovar el access_token
    token_type: str = 'bearer'  # Tipo estándar de token HTTP — siempre 'bearer'


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


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=150)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=6, max_length=50)
    confirm_password: str = Field(min_length=6, max_length=50)

    @model_validator(mode='after')
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Las contraseñas no coinciden')
        if len(self.new_password.encode('utf-8')) > 72:
            raise ValueError('La contraseña excede el límite admitido')
        return self

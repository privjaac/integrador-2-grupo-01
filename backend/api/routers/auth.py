# ==============================================================================
# ROUTERS/AUTH.PY — Endpoints de autenticación
#
# Maneja todo lo relacionado al login y tokens de sesión.
#
# Endpoints:
#   POST /api/auth/login    → recibe usuario y contraseña, devuelve tokens
#   POST /api/auth/refresh  → recibe refresh_token, devuelve nuevo access_token
#   POST /api/auth/logout   → invalida la sesión (el frontend borra los tokens)
#
# Flujo de login:
#   1. React manda username + password
#   2. FastAPI busca el colaborador en PostgreSQL por username
#   3. Verifica la contraseña contra el hash guardado con bcrypt
#   4. Si es correcto, genera access_token y refresh_token con JWT
#   5. Devuelve los tokens a React
#   6. React los guarda y los manda en cada petición siguiente
# ==============================================================================

from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from django.conf import settings

from api.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, AuthUser
from clients.models import Collaborator


router = APIRouter()


# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE BCRYPT
#
# CryptContext maneja el encriptado y verificación de contraseñas.
# schemes=['bcrypt'] → usa el algoritmo bcrypt para hashear.
# deprecated='auto' → si en el futuro cambiamos el algoritmo,
#   bcrypt queda marcado como antiguo automáticamente.
# ------------------------------------------------------------------------------
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


# ------------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compara una contraseña en texto plano con su hash guardado en BD.
    Devuelve True si coinciden, False si no.
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """
    Convierte una contraseña en texto plano a su hash bcrypt.
    Se usa al crear o cambiar contraseña de un colaborador.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """
    Genera un JWT de corta duración (30 minutos por defecto).
    'data' contiene la info que queremos guardar en el token:
    username, rol y collaborator_id.
    """
    to_encode = data.copy()

    # Fecha de expiración = ahora + 30 minutos
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # 'exp' es un campo estándar de JWT — indica cuándo vence el token
    to_encode.update({'exp': expire, 'type': 'access'})

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(data: dict) -> str:
    """
    Genera un JWT de larga duración (24 horas por defecto).
    Mismo proceso que el access_token pero con más tiempo de vida.
    """
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        hours=settings.REFRESH_TOKEN_EXPIRE_HOURS
    )

    to_encode.update({'exp': expire, 'type': 'refresh'})

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    """
    Verifica y decodifica un JWT.
    Si el token es inválido, fue modificado o venció → lanza excepción 401.
    Devuelve el contenido del token si es válido.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token inválido o expirado',
            headers={'WWW-Authenticate': 'Bearer'},
        )


# ------------------------------------------------------------------------------
# ENDPOINT: POST /api/auth/login
#
# Recibe username y password, verifica credenciales y devuelve los tokens.
#
# Respuestas:
#   200 → login exitoso, devuelve access_token y refresh_token
#   401 → usuario no existe o contraseña incorrecta
#   403 → colaborador inactivo (is_active = False)
# ------------------------------------------------------------------------------
@router.post('/login', response_model=TokenResponse)
def login(data: LoginRequest):

    # Buscar el colaborador por username en PostgreSQL
    collaborator = Collaborator.objects.filter(username=data.username).first()

    # Si no existe el usuario o la contraseña no coincide → error 401
    # Mensaje genérico a propósito para no revelar si el usuario existe
    if not collaborator or not verify_password(data.password, collaborator.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Usuario o contraseña incorrectos'
        )

    # Si el colaborador está inactivo no puede acceder
    # is_active = False → dado de baja del sistema
    if not collaborator.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Tu cuenta está inactiva. Contacta al administrador.'
        )

    # Datos que se guardan dentro del token
    token_data = {
        'sub': collaborator.username,
        'role': collaborator.role.level if collaborator.role else None,
        'collaborator_id': collaborator.id
    }

    # Generar ambos tokens
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=AuthUser(
            id=collaborator.id,
            cupe=collaborator.cupe,
            username=collaborator.username,
            first_name=collaborator.first_name,
            last_name=collaborator.last_name,
            email=collaborator.email,
            role=collaborator.role.level if collaborator.role else None,
            role_name=collaborator.role.name if collaborator.role else None,
            is_active=collaborator.is_active,
        )
    )


# ------------------------------------------------------------------------------
# ENDPOINT: POST /api/auth/refresh
#
# Recibe el refresh_token y devuelve un nuevo access_token.
# React llama a este endpoint cuando el access_token vence (cada 30 min).
#
# Respuestas:
#   200 → devuelve nuevo access_token
#   401 → refresh_token inválido o expirado
# ------------------------------------------------------------------------------
@router.post('/refresh', response_model=TokenResponse)
def refresh_token(data: RefreshRequest):

    # Verificar que el refresh_token sea válido
    payload = decode_token(data.refresh_token)

    # Verificar que sea un refresh_token y no un access_token
    if payload.get('type') != 'refresh':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token inválido'
        )

    # Verificar que el colaborador siga existiendo y esté activo
    collaborator = Collaborator.objects.filter(
        username=payload.get('sub')
    ).first()

    if not collaborator or not collaborator.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Usuario no encontrado o inactivo'
        )

    # Generar nuevo access_token con los mismos datos
    token_data = {
        'sub': collaborator.username,
        'role': collaborator.role.level if collaborator.role else None,
        'collaborator_id': collaborator.id
    }

    new_access_token = create_access_token(token_data)

    # El refresh_token se reutiliza — no generamos uno nuevo
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=data.refresh_token
    )


# ------------------------------------------------------------------------------
# ENDPOINT: POST /api/auth/logout
#
# El logout en JWT es responsabilidad del frontend — simplemente borra
# los tokens guardados en memoria.
#
# Este endpoint existe para que React tenga una URL a donde llamar
# al hacer logout. En el futuro se puede agregar una blacklist de tokens.
# ------------------------------------------------------------------------------
@router.post('/logout')
def logout():
    return {'message': 'Sesión cerrada correctamente'}
"""Authentication, independently revocable sessions and own-account recovery."""
import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from fastapi import BackgroundTasks, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from api.router import APIRouter
from api.schemas.auth import (
    ForgotPasswordRequest, LoginRequest, PasswordResetRequest, RefreshRequest,
    TokenResponse, LogoutRequest,
)
from clients.models import Collaborator, CollaboratorSession, PasswordResetRequest as PasswordResetRecord

router = APIRouter()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
GENERIC_RECOVERY_MESSAGE = 'Si el correo corresponde a una cuenta activa, recibirá instrucciones para recuperar el acceso.'


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    claims = data.copy()
    claims.update({'exp': timezone.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), 'type': 'access'})
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict, jti: str | None = None, expires=None) -> tuple[str, object]:
    expires = expires or (timezone.now() + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS))
    claims = data.copy()
    claims.update({'exp': expires, 'type': 'refresh', 'jti': jti or secrets.token_urlsafe(32)})
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM), expires


def decode_token(token: str, *, verify_exp: bool = True) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={'verify_exp': verify_exp})
    except JWTError:
        raise HTTPException(status_code=401, detail='Token inválido o expirado', headers={'WWW-Authenticate': 'Bearer'})


def _token_pair(collaborator: Collaborator, session_id: uuid.UUID, refresh_jti: str, refresh_expires=None):
    data = {'sub': collaborator.username, 'role': collaborator.role.level if collaborator.role else None,
            'collaborator_id': collaborator.id, 'sid': str(session_id)}
    refresh, expiry = create_refresh_token(data, refresh_jti, refresh_expires)
    return create_access_token(data), refresh, expiry


@router.post('/login', response_model=TokenResponse)
def login(data: LoginRequest):
    collaborator = Collaborator.objects.select_related('role').filter(username=data.username).first()
    if not collaborator or not verify_password(data.password, collaborator.password_hash):
        raise HTTPException(status_code=401, detail='Usuario o contraseña incorrectos')
    if not collaborator.is_active:
        raise HTTPException(status_code=403, detail='Tu cuenta está inactiva. Contacta al administrador.')
    if collaborator.role is None or not collaborator.role.is_active:
        raise HTTPException(status_code=403, detail='El rol organizacional de tu cuenta está inactivo.')
    session_id, jti = uuid.uuid4(), secrets.token_urlsafe(32)
    access, refresh, expiry = _token_pair(collaborator, session_id, jti)
    CollaboratorSession.objects.create(id=session_id, collaborator=collaborator, refresh_jti=jti, expires_at=expiry)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post('/refresh', response_model=TokenResponse)
def refresh_token(data: RefreshRequest):
    payload = decode_token(data.refresh_token)
    if payload.get('type') != 'refresh' or not payload.get('sid') or not payload.get('jti'):
        raise HTTPException(status_code=401, detail='Token inválido')
    try:
        session_id = uuid.UUID(payload['sid'])
        collaborator_id = int(payload['collaborator_id'])
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=401, detail='Token inválido')
    with transaction.atomic():
        session = CollaboratorSession.objects.select_for_update().filter(id=session_id).first()
        if (not session or session.revoked_at or session.expires_at <= timezone.now()
                or session.refresh_jti != payload['jti'] or session.collaborator_id != collaborator_id):
            raise HTTPException(status_code=401, detail='Sesión inválida o revocada')
        collaborator = Collaborator.objects.select_related('role').filter(
            id=collaborator_id, is_active=True, role__is_active=True,
        ).first()
        if not collaborator:
            raise HTTPException(status_code=401, detail='Usuario no encontrado o inactivo')
        new_jti = secrets.token_urlsafe(32)
        # Rotation invalidates the previous credential but does not extend the
        # original 24-hour session lifetime through periodic background refresh.
        access, refresh, expiry = _token_pair(collaborator, session_id, new_jti, session.expires_at)
        session.refresh_jti = new_jti
        session.expires_at = expiry
        session.save(update_fields=['refresh_jti', 'expires_at', 'last_activity_at'])
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post('/logout')
def logout(data: LogoutRequest):
    payload = decode_token(data.refresh_token, verify_exp=False)
    if payload.get('type') != 'refresh' or not payload.get('sid') or not payload.get('jti'):
        raise HTTPException(status_code=401, detail='Token inválido')
    try:
        session_id = uuid.UUID(payload['sid'])
        collaborator_id = int(payload['collaborator_id'])
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail='Token inválido')
    with transaction.atomic():
        session = CollaboratorSession.objects.select_for_update().filter(
            id=session_id, collaborator_id=collaborator_id,
        ).first()
        if not session:
            raise HTTPException(status_code=401, detail='Sesión inválida')
        if not session.revoked_at:
            session.revoked_at = timezone.now()
            session.save(update_fields=['revoked_at'])
    return {'message': 'Sesión cerrada correctamente'}


def deliver_recovery_email(recipient: str, token: str, *, reset: bool = False):
    """Send through configured Django email backend; do not log secrets."""
    base_url = getattr(settings, 'FRONTEND_PUBLIC_URL', '').rstrip('/')
    subject = 'ELISA: contraseña actualizada' if reset else 'ELISA: recuperar acceso'
    body = ('Su contraseña fue actualizada.' if reset else
            f'Para restablecer su contraseña, abra: {base_url}/reset-password/{token}\nEl enlace vence en una hora y solo puede usarse una vez.')
    try:
        if not settings.DEFAULT_FROM_EMAIL or (not reset and not base_url):
            return False
        return bool(send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False))
    except Exception:
        return False


@router.post('/forgot-password', status_code=202)
def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    collaborator = Collaborator.objects.filter(email__iexact=data.email, is_active=True).first()
    if collaborator:
        raw_token = secrets.token_urlsafe(32)
        record = PasswordResetRecord.objects.create(
            collaborator=collaborator,
            token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        # Delivery happens after response; if mail is unavailable, invalidate the undisclosed token.
        background_tasks.add_task(_deliver_and_revoke_if_failed, record.id, collaborator.email, raw_token)
    return {'message': GENERIC_RECOVERY_MESSAGE}


def _deliver_and_revoke_if_failed(record_id, email, token):
    sent = deliver_recovery_email(email, token)
    if not sent:
        PasswordResetRecord.objects.filter(id=record_id, used_at__isnull=True).update(revoked_at=timezone.now())


@router.put('/reset-password')
def reset_password(data: PasswordResetRequest, background_tasks: BackgroundTasks):
    digest = hashlib.sha256(data.token.encode()).hexdigest()
    with transaction.atomic():
        request = PasswordResetRecord.objects.select_for_update().select_related('collaborator').filter(token_digest=digest).first()
        now = timezone.now()
        if (not request or request.used_at or request.revoked_at or request.expires_at <= now
                or not request.collaborator.is_active):
            raise HTTPException(status_code=400, detail='Enlace inválido o expirado')
        collaborator = Collaborator.objects.select_for_update().get(pk=request.collaborator_id)
        collaborator.password_hash = hash_password(data.new_password)
        collaborator.save(update_fields=['password_hash', 'updated_at'])
        # Password replacement and account-wide session revocation commit as
        # one unit; unrelated collaborators and their sessions are untouched.
        CollaboratorSession.objects.filter(
            collaborator_id=collaborator.pk, revoked_at__isnull=True,
        ).update(revoked_at=now)
        request.used_at = now
        request.save(update_fields=['used_at'])
        email = collaborator.email
    background_tasks.add_task(deliver_recovery_email, email, '', reset=True)
    return {'message': 'La contraseña fue actualizada correctamente.'}

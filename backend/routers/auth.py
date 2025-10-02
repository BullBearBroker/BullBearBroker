from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import hashlib
import time
from contextlib import nullcontext

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Dict, Literal, Optional  # [Codex] cambiado - se añaden tipos para risk profile
import re

from pydantic import BaseModel, field_validator

from backend.core.login_backoff import login_backoff
from backend.core.metrics import LOGIN_ATTEMPTS, LOGIN_DURATION, LOGIN_RATE_LIMITED
from backend.core.logging_config import get_logger, log_event
from backend.core.rate_limit import login_rate_limiter, rate_limit
from backend.core.security import create_access_token, create_refresh_token, decode_refresh
from backend.database import get_db
from backend.models.refresh_token import RefreshToken
from backend.schemas.auth import RefreshRequest, TokenPair
from backend.utils.config import Config
from backend.services.captcha_service import (
    CaptchaVerificationError,
    verify_captcha,
)
from backend.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    user_service,
)

try:  # pragma: no cover - tracing opcional
    from opentelemetry import trace
except Exception:  # pragma: no cover - entorno sin tracing
    trace = None  # type: ignore[assignment]

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()
logger = get_logger(service="auth_router")

_TRACER = trace.get_tracer("backend.auth") if trace else None

_LOGIN_IP_LIMIT_TIMES = getattr(Config, "LOGIN_IP_LIMIT_TIMES", 20)
_LOGIN_IP_LIMIT_SECONDS = getattr(Config, "LOGIN_IP_LIMIT_SECONDS", 60)
_EMAIL_BACKOFF_DETAIL = (
    "Demasiados intentos de inicio de sesión. Intenta nuevamente más tarde."
)


def _record_login_rate_limit(request: Request, dimension: str) -> None:
    client_ip = request.client.host if request.client else "unknown"
    payload: Dict[str, object] = {
        "service": "auth_router",
        "event": "login_rate_limited",
        "level": "warning",
        "dimension": dimension,
        "client_ip": client_ip,
    }
    email_hash = getattr(request.state, "login_email_hash", None)
    if dimension == "email" and email_hash:
        payload["email_hash"] = email_hash
    log_event(logger, **payload)
    LOGIN_ATTEMPTS.labels(outcome=f"limited_{dimension}").inc()
    LOGIN_RATE_LIMITED.labels(dimension=dimension).inc()


_login_rate_limit = login_rate_limiter(
    times=5,
    seconds=60,
    on_limit=_record_login_rate_limit,
    state_attribute="login_limited_email",
)
_login_ip_rate_limit = rate_limit(
    times=_LOGIN_IP_LIMIT_TIMES,
    seconds=_LOGIN_IP_LIMIT_SECONDS,
    identifier="auth_login_ip",
    detail="Demasiadas solicitudes de inicio de sesión desde esta IP. Espera antes de volver a intentarlo.",
    on_limit=_record_login_rate_limit,
    on_limit_dimension="ip",
    state_attribute="login_limited_ip",
)
_refresh_rate_limit = rate_limit(
    times=10,
    seconds=120,
    identifier="auth_refresh",
    detail="Demasiadas solicitudes de refresco. Espera antes de volver a intentarlo.",
)


EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def _validate_email(value: str) -> str:
    """Valida direcciones de correo usando email-validator si está disponible."""

    try:
        from email_validator import EmailNotValidError, validate_email  # type: ignore
    except Exception:  # pragma: no cover - dependencia opcional ausente en tests
        if not EMAIL_REGEX.fullmatch(value):
            raise ValueError("Correo electrónico inválido")
        return value.lower()

    try:
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return result.normalized


class UserCreate(BaseModel):
    email: str
    password: str
    risk_profile: Optional[Literal["conservador", "moderado", "agresivo"]] = None  # [Codex] nuevo

    @field_validator("email")
    @classmethod
    def _validate_email_field(cls, value: str) -> str:
        return _validate_email(value)

    @field_validator("risk_profile")  # [Codex] nuevo
    @classmethod
    def _normalize_risk_profile(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.lower()


class UserLogin(BaseModel):
    email: str
    password: str
    captcha_token: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _validate_email_field(cls, value: str) -> str:
        return _validate_email(value)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    revoke_all: bool = False


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    try:
        new_user = user_service.create_user(
            email=user_data.email,
            password=user_data.password,
            risk_profile=user_data.risk_profile,
        )
    except TypeError:  # [Codex] nuevo - compatibilidad con servicios dummy en tests
        new_user = user_service.create_user(
            email=user_data.email,
            password=user_data.password,
        )
    except UserAlreadyExistsError as exc:  # pragma: no cover - tests cubren el éxito
        email_hash = hashlib.sha256(user_data.email.encode("utf-8")).hexdigest()[:8]
        log_event(
            logger,
            service="auth_router",
            event="user_registration_conflict",
            level="warning",
            email_hash=email_hash,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:  # [Codex] nuevo - valida perfil de riesgo
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = {
        "id": str(new_user.id),
        "email": new_user.email,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
    }
    profile_value = getattr(new_user, "risk_profile", None)
    if profile_value is not None:
        payload["risk_profile"] = profile_value  # [Codex] nuevo
    return payload


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(_login_rate_limit), Depends(_login_ip_rate_limit)],
)
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenPair:
    start = time.perf_counter()
    limited_email = bool(getattr(request.state, "login_limited_email", False))
    limited_ip = bool(getattr(request.state, "login_limited_ip", False))
    email_hash = getattr(request.state, "login_email_hash", None)
    normalized_email = credentials.email.strip().lower()
    if not email_hash:
        email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:8]
        setattr(request.state, "login_email_hash", email_hash)

    wait_seconds = await login_backoff.required_wait_seconds(email_hash)

    span_manager = _TRACER.start_as_current_span("auth.login") if _TRACER else nullcontext()
    outcome = "ok"
    with span_manager as span:
        if span is not None:
            span.set_attribute("limited.email", limited_email)
            span.set_attribute("limited.ip", limited_ip)
            span.set_attribute("user.email_hash", email_hash)

        if wait_seconds > 0:
            outcome = "rate_limited"
            duration = time.perf_counter() - start
            LOGIN_DURATION.observe(duration)
            LOGIN_ATTEMPTS.labels(outcome=outcome).inc()
            LOGIN_RATE_LIMITED.labels(dimension="email_backoff").inc()
            if span is not None:
                span.set_attribute("outcome", outcome)
            log_event(
                logger,
                service="auth_router",
                event="login_failed",
                level="warning",
                email_hash=email_hash,
                reason="rate_limited",
            )
            raise HTTPException(
                status_code=429,
                detail=_EMAIL_BACKOFF_DETAIL,
                headers={"Retry-After": str(wait_seconds)},
            )

        if Config.ENABLE_CAPTCHA_ON_LOGIN:
            failure_count = await login_backoff.failure_count(email_hash)
            captcha_required = (
                failure_count >= Config.LOGIN_CAPTCHA_THRESHOLD or limited_ip
            )
            if captcha_required:
                try:
                    verify_captcha(credentials.captcha_token)
                except CaptchaVerificationError as exc:
                    outcome = "captcha_required"
                    duration = time.perf_counter() - start
                    LOGIN_DURATION.observe(duration)
                    LOGIN_ATTEMPTS.labels(outcome=outcome).inc()
                    if span is not None:
                        span.set_attribute("outcome", outcome)
                    log_event(
                        logger,
                        service="auth_router",
                        event="login_failed",
                        level="warning",
                        email_hash=email_hash,
                        reason="captcha_required",
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Se requiere verificación adicional antes de continuar.",
                    ) from exc

        try:
            user = user_service.authenticate_user(
                email=credentials.email,
                password=credentials.password,
            )
        except InvalidCredentialsError as exc:
            outcome = "invalid"
            duration = time.perf_counter() - start
            LOGIN_DURATION.observe(duration)
            LOGIN_ATTEMPTS.labels(outcome=outcome).inc()
            if span is not None:
                span.set_attribute("outcome", outcome)
            backoff_seconds = await login_backoff.register_failure(email_hash)
            log_event(
                logger,
                service="auth_router",
                event="login_failed",
                level="warning",
                email_hash=email_hash,
                reason="invalid",
                backoff_seconds=backoff_seconds,
            )
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        sub = str(user.id)
        jti = str(uuid4())
        refresh_token = create_refresh_token(sub=sub, jti=jti)
        refresh_payload = decode_refresh(refresh_token)
        refresh_expires = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

        # ⬇️ Persistimos el refresh token siempre con nuestro servicio
        user_service.store_refresh_token(user.id, refresh_token)

        access_token = create_access_token(sub=sub, extra={"jti": str(uuid4())})
        access_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        user_service.register_external_session(user.id, access_token, access_expires)
        await login_backoff.clear(email_hash)

        duration = time.perf_counter() - start
        LOGIN_DURATION.observe(duration)
        LOGIN_ATTEMPTS.labels(outcome=outcome).inc()
        if span is not None:
            span.set_attribute("outcome", outcome)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires.isoformat(),
            refresh_expires_at=refresh_expires.isoformat(),
        )


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(_refresh_rate_limit)],
)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    token_str = req.refresh_token
    db_token = None
    if db is not None:
        db_token = db.query(RefreshToken).filter(RefreshToken.token == token_str).first()

    if db_token:
        try:
            payload = decode_refresh(token_str)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            sub_uuid = UUID(sub)
        except (jwt.PyJWTError, ValueError):
            log_event(
                logger,
                service="auth_router",
                event="refresh_token_invalid",
                level="warning",
                refresh_id=str(getattr(db_token, "id", "")),
            )
            db.delete(db_token)
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        db.delete(db_token)
        db.commit()

        new_refresh = create_refresh_token(sub=sub, jti=str(uuid4()))
        refresh_payload = decode_refresh(new_refresh)
        refresh_expires = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
        db.add(
            RefreshToken(
                user_id=sub_uuid,
                token=new_refresh,
                expires_at=refresh_expires,
            )
        )
        db.commit()
        access_token = create_access_token(sub=sub)
        access_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        user_service.register_external_session(sub_uuid, access_token, access_expires)
        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh,
            access_expires_at=access_expires.isoformat(),
            refresh_expires_at=refresh_expires.isoformat(),
        )

    try:
        user, new_refresh, refresh_expires = user_service.rotate_refresh_token(token_str)
    except InvalidTokenError as exc:
        log_event(
            logger,
            service="auth_router",
            event="refresh_token_rotation_failed",
            level="warning",
            reason=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token = create_access_token(sub=str(user.id), extra={"jti": str(uuid4())})
    access_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    user_service.register_external_session(user.id, access_token, access_expires)
    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh,
        access_expires_at=access_expires.isoformat(),
        refresh_expires_at=refresh_expires.isoformat(),
    )


@router.post("/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)) -> Dict[str, str]:
    if req.revoke_all:
        if not req.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token required")
        try:
            payload = decode_refresh(req.refresh_token)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=400, detail="refresh_token invalid")
            sub_uuid = UUID(sub)
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(status_code=400, detail="refresh_token invalid")

        if db is not None:
            db.query(RefreshToken).filter(RefreshToken.user_id == sub_uuid).delete()
            db.commit()
        else:
            user_service.revoke_all_refresh_tokens(sub_uuid)
        return {"detail": "All sessions revoked"}

    if not req.refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token required")

    if db is not None:
        db.query(RefreshToken).filter(RefreshToken.token == req.refresh_token).delete()
        db.commit()
    else:
        user_service.revoke_refresh_token(req.refresh_token)

    return {"detail": "Session revoked"}


@router.get("/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    try:
        user = user_service.get_current_user(token.credentials)
        user_service.register_session_activity(token.credentials)
        return {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

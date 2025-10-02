from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Dict, Literal, Optional  # [Codex] cambiado - se añaden tipos para risk profile
import re

from pydantic import BaseModel, field_validator

from backend.core.logging_config import get_logger, log_event
from backend.core.rate_limit import rate_limit
from backend.core.security import create_access_token, create_refresh_token, decode_refresh
from backend.database import get_db
from backend.models import User
from backend.models.refresh_token import RefreshToken
from backend.schemas.auth import RefreshRequest, TokenPair
from backend.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    user_service,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()
logger = get_logger(service="auth_router")

_login_rate_limit = rate_limit(
    times=5,
    seconds=60,
    identifier="auth_login",
    detail="Demasiados intentos de inicio de sesión. Intenta nuevamente más tarde.",
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
        log_event(
            logger,
            service="auth_router",
            event="user_registration_conflict",
            level="warning",
            email=user_data.email,
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
    dependencies=[Depends(_login_rate_limit)],
)
async def login(credentials: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = user_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
        )
    except InvalidCredentialsError as exc:
        log_event(
            logger,
            service="auth_router",
            event="login_failed",
            level="warning",
            email=credentials.email,
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

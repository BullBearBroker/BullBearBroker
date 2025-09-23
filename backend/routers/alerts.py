"""User alert management routes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Literal, Optional, List
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator

USER_SERVICE_ERROR: Optional[Exception] = None

try:  # pragma: no cover - allow running from different entrypoints
    from backend.models import Alert, User
    from backend.services.user_service import UserNotFoundError, user_service
    from backend.utils.config import Config
except RuntimeError as exc:  # pragma: no cover - missing configuration
    from backend.models import Alert, User  # type: ignore
    from backend.utils.config import Config  # type: ignore

    user_service = None  # type: ignore[assignment]
    UserNotFoundError = RuntimeError  # type: ignore[assignment]
    USER_SERVICE_ERROR = exc
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.models import Alert, User  # type: ignore
    from backend.utils.config import Config  # type: ignore

    try:
        from backend.services.user_service import (  # type: ignore
            UserNotFoundError,
            user_service,
        )
    except RuntimeError as exc:  # pragma: no cover - missing configuration
        user_service = None  # type: ignore[assignment]
        UserNotFoundError = RuntimeError  # type: ignore[assignment]
        USER_SERVICE_ERROR = exc

router = APIRouter(prefix="/alerts", tags=["Alerts"])
security = HTTPBearer()

SECRET_KEY = Config.JWT_SECRET_KEY
ALGORITHM = Config.JWT_ALGORITHM


class AlertCreate(BaseModel):
    asset: str = Field(..., min_length=1, max_length=50)
    value: float = Field(..., description="Precio objetivo de la alerta")
    condition: Literal["<", ">", "=="] = Field(
        ">", description="Condición de activación"
    )

    @validator("asset")
    def _strip_asset(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El símbolo del activo es obligatorio")
        return cleaned.upper()


class AlertResponse(BaseModel):
    id: str
    asset: str
    condition: str
    value: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, alert: Alert) -> "AlertResponse":
        return cls(
            id=str(alert.id),
            asset=alert.asset,
            condition=alert.condition,
            value=alert.value,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )


def _ensure_user_service_available() -> None:
    if user_service is None:
        detail = "Servicio de usuarios no disponible"
        if USER_SERVICE_ERROR is not None:
            detail = f"{detail}. {USER_SERVICE_ERROR}"
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    _ensure_user_service_available()

    try:
        payload: dict[str, Any] = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover - depends on runtime
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    email = payload.get("sub")
    raw_user_id = payload.get("user_id")
    if not email or raw_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        token_user_id = UUID(str(raw_user_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    user = await asyncio.to_thread(user_service.get_user_by_email, email)
    if not user or user.id != token_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

    return user


@router.get("", response_model=List[AlertResponse])
async def list_alerts(current_user: User = Depends(get_current_user)) -> List[AlertResponse]:
    """List alerts for the authenticated user."""

    _ensure_user_service_available()

    alerts = await asyncio.to_thread(user_service.get_alerts_for_user, current_user.id)
    return [AlertResponse.from_model(alert) for alert in alerts]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_in: AlertCreate, current_user: User = Depends(get_current_user)
) -> AlertResponse:
    """Create a new alert associated with the authenticated user."""

    _ensure_user_service_available()

    try:
        alert = await asyncio.to_thread(
            user_service.create_alert,
            current_user.id,
            asset=alert_in.asset,
            value=alert_in.value,
            condition=alert_in.condition,
        )
    except UserNotFoundError as exc:  # pragma: no cover - defensive safety
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AlertResponse.from_model(alert)

"""User alert management routes."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

USER_SERVICE_ERROR: Optional[Exception] = None

try:  # pragma: no cover - allow running from different entrypoints
    from backend.models import Alert, User
    from backend.services.alert_service import alert_service
    from backend.services.user_service import (
        InvalidTokenError,
        UserNotFoundError,
        user_service,
    )
except RuntimeError as exc:  # pragma: no cover - missing configuration
    from backend.models import Alert, User  # type: ignore

    user_service = None  # type: ignore[assignment]
    UserNotFoundError = RuntimeError  # type: ignore[assignment]
    InvalidTokenError = RuntimeError  # type: ignore[assignment]
    USER_SERVICE_ERROR = exc
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.models import Alert, User  # type: ignore

    try:
        from backend.services.alert_service import alert_service  # type: ignore
        from backend.services.user_service import (  # type: ignore
            InvalidTokenError,
            UserNotFoundError,
            user_service,
        )
    except RuntimeError as exc:  # pragma: no cover - missing configuration
        user_service = None  # type: ignore[assignment]
        UserNotFoundError = RuntimeError  # type: ignore[assignment]
        InvalidTokenError = RuntimeError  # type: ignore[assignment]
        USER_SERVICE_ERROR = exc
    except ImportError:  # pragma: no cover - fallback when running from app package
        from services.alert_service import alert_service  # type: ignore

from backend.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertSuggestionPayload,
    AlertSuggestionResult,
    AlertUpdate,
)
from backend.utils.config import Config

# 👇 sin prefix aquí
router = APIRouter(tags=["alerts"])
security = HTTPBearer()


class AlertDispatchRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    telegram_chat_id: Optional[str] = None
    discord_channel_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El mensaje no puede estar vacío")
        return cleaned

    @field_validator("telegram_chat_id", "discord_channel_id")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


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
        return await asyncio.to_thread(
            user_service.get_current_user, credentials.credentials
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("", response_model=List[AlertResponse])
async def list_alerts(current_user: User = Depends(get_current_user)) -> List[AlertResponse]:
    """List alerts for the authenticated user."""

    _ensure_user_service_available()

    alerts = await asyncio.to_thread(user_service.get_alerts_for_user, current_user.id)
    return [AlertResponse.from_orm(alert) for alert in alerts]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_in: AlertCreate, current_user: User = Depends(get_current_user)
) -> AlertResponse:
    """Create a new alert associated with the authenticated user."""

    _ensure_user_service_available()

    if not alert_in.asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'asset' es obligatorio",
        )

    try:
        alert_service.validate_condition_expression(alert_in.condition)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    normalized_value = alert_in.value if alert_in.value is not None else 0.0
    normalized_active = alert_in.active if alert_in.active is not None else True

    try:
        alert = await asyncio.to_thread(
            user_service.create_alert,
            current_user.id,
            title=alert_in.title,
            asset=alert_in.asset,
            value=normalized_value,
            condition=alert_in.condition,
            active=normalized_active,
        )
    except UserNotFoundError as exc:  # pragma: no cover - defensive safety
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AlertResponse.from_orm(alert)


@router.post("/suggest", response_model=AlertSuggestionResult)
async def suggest_alert_condition(
    payload: AlertSuggestionPayload, current_user: User = Depends(get_current_user)
) -> AlertSuggestionResult:
    """Genera una condición sugerida reforzada con IA para agilizar la creación de alertas."""  # [Codex] nuevo

    _ensure_user_service_available()

    suggestion = await alert_service.suggest_alert_condition(
        payload.asset,
        payload.interval or "1h",
    )
    return AlertSuggestionResult(**suggestion)


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete an alert owned by the authenticated user."""

    _ensure_user_service_available()

    deleted = await asyncio.to_thread(
        user_service.delete_alert_for_user, current_user.id, alert_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada o no pertenece al usuario",
        )

    return {"message": "Alerta eliminada exitosamente", "id": str(alert_id)}


@router.put("/{alert_id}", response_model=AlertResponse, status_code=status.HTTP_200_OK)
async def update_alert(
    alert_id: UUID,
    alert_in: AlertUpdate,
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """Update an existing alert owned by the authenticated user."""

    _ensure_user_service_available()

    if alert_in.condition is not None:
        try:
            alert_service.validate_condition_expression(alert_in.condition)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        alert = await asyncio.to_thread(
            user_service.update_alert,
            current_user.id,
            alert_id,
            title=alert_in.title,
            asset=alert_in.asset,
            value=alert_in.value,
            condition=alert_in.condition,
            active=alert_in.active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AlertResponse.from_orm(alert)


@router.post("/send", status_code=status.HTTP_200_OK)
async def send_alert_notification(
    payload: AlertDispatchRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Dict[str, str]]:
    """Trigger an immediate alert notification via Telegram and/or Discord."""

    _ensure_user_service_available()

    telegram_target = payload.telegram_chat_id or Config.TELEGRAM_DEFAULT_CHAT_ID
    discord_target = payload.discord_channel_id

    if not (telegram_target or discord_target):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes especificar al menos un canal de notificación",
        )

    try:
        return await alert_service.send_external_alert(
            message=payload.message,
            telegram_chat_id=telegram_target,
            discord_channel_id=discord_target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_all_alerts(current_user: User = Depends(get_current_user)) -> dict:
    """Delete all alerts for the authenticated user."""

    _ensure_user_service_available()

    await asyncio.to_thread(user_service.delete_all_alerts_for_user, current_user.id)

    return {"message": "Todas las alertas fueron eliminadas exitosamente"}

"""User alert management routes."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from backend.core.logging_config import get_logger, log_event
from backend.core.metrics import ALERTS_RATE_LIMITED
from backend.core.rate_limit import rate_limit
from backend.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertSuggestionPayload,
    AlertSuggestionResult,
    AlertUpdate,
)
from backend.utils.config import Config

USER_SERVICE_ERROR: Exception | None = None

try:  # pragma: no cover - allow running from different entrypoints
    from backend.models import User
    from backend.services.alert_service import alert_service
    from backend.services.user_service import (
        InvalidTokenError,
        UserNotFoundError,
        user_service,
    )
except RuntimeError as exc:  # pragma: no cover - missing configuration
    from backend.models import User  # type: ignore

    user_service = None  # type: ignore[assignment]
    UserNotFoundError = RuntimeError  # type: ignore[assignment]
    InvalidTokenError = RuntimeError  # type: ignore[assignment]
    USER_SERVICE_ERROR = exc
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.models import User  # type: ignore

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

# 👇 sin prefix aquí
router = APIRouter(tags=["alerts"])
security = HTTPBearer()
logger = get_logger(service="alerts_router")


def _record_alert_rate_limit(request: Request, action: str) -> None:
    payload: dict[str, object] = {
        "service": "alerts_router",
        "event": "alerts_rate_limited",
        "level": "warning",
        "action": action,
        "client_ip": request.client.host if request.client else "unknown",
    }
    log_event(logger, **payload)
    ALERTS_RATE_LIMITED.labels(action=action).inc()


_create_alert_rate_limit = rate_limit(
    times=10,
    seconds=60,
    identifier="alerts_create",
    detail="Demasiadas alertas creadas. Intenta más tarde.",
    fallback_times=50,
    on_limit=_record_alert_rate_limit,
    on_limit_dimension="create",
)
_dispatch_alert_rate_limit = rate_limit(
    times=5,
    seconds=60,
    identifier="alerts_dispatch",
    detail="Demasiadas alertas enviadas. Reduce la frecuencia.",
    on_limit=_record_alert_rate_limit,
    on_limit_dimension="dispatch",
)


class AlertDispatchRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    telegram_chat_id: str | None = None
    discord_channel_id: str | None = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El mensaje no puede estar vacío")
        return cleaned

    @field_validator("telegram_chat_id", "discord_channel_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


def _ensure_user_service_available() -> None:
    if user_service is None:
        detail = "Servicio de usuarios no disponible"
        if USER_SERVICE_ERROR is not None:
            detail = f"{detail}. {USER_SERVICE_ERROR}"
        log_event(
            logger,
            service="alerts_router",
            event="user_service_unavailable",
            level="error",
            detail=detail,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    _ensure_user_service_available()

    try:
        return await asyncio.to_thread(
            user_service.get_current_user, credentials.credentials
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AlertResponse]:
    """List alerts for the authenticated user."""

    _ensure_user_service_available()

    alerts = await asyncio.to_thread(user_service.get_alerts_for_user, current_user.id)
    return [AlertResponse.from_orm(alert) for alert in alerts]


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_create_alert_rate_limit)],
)
async def create_alert(
    alert_in: AlertCreate,
    current_user: Annotated[User, Depends(get_current_user)],
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

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
        log_event(
            logger,
            service="alerts_router",
            event="alert_create_user_missing",
            level="warning",
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        log_event(
            logger,
            service="alerts_router",
            event="alert_create_invalid_payload",
            level="warning",
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return AlertResponse.from_orm(alert)


@router.post("/suggest", response_model=AlertSuggestionResult)
async def suggest_alert_condition(
    payload: AlertSuggestionPayload,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertSuggestionResult:
    """Genera una condición sugerida reforzada con IA para agilizar
    la creación de alertas."""  # [Codex] nuevo

    _ensure_user_service_available()

    suggestion = await alert_service.suggest_alert_condition(
        payload.asset,
        payload.interval or "1h",
    )
    return AlertSuggestionResult(**suggestion)


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return AlertResponse.from_orm(alert)


@router.post(
    "/send",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_dispatch_alert_rate_limit)],
)
async def send_alert_notification(
    payload: AlertDispatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, dict[str, str]]:
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
        log_event(
            logger,
            service="alerts_router",
            event="alert_dispatch_validation_error",
            level="warning",
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        log_event(
            logger,
            service="alerts_router",
            event="alert_dispatch_failure",
            level="error",
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_all_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Delete all alerts for the authenticated user."""

    _ensure_user_service_available()

    await asyncio.to_thread(user_service.delete_all_alerts_for_user, current_user.id)

    return {"message": "Todas las alertas fueron eliminadas exitosamente"}

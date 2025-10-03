"""REST endpoints for managing both classic and advanced alerts."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError, field_validator

from backend.core.logging_config import get_logger, log_event
from backend.core.metrics import ALERTS_RATE_LIMITED
from backend.core.rate_limit import rate_limiter
from backend.models import Alert, User
from backend.schemas.alerts import AlertCreate, AlertToggle, AlertUpdate
from backend.services.alert_service import alert_service
from backend.services.alerts_service import alerts_service
from backend.utils.config import Config

try:  # pragma: no cover - fallback when user service is unavailable
    from backend.services.user_service import (  # type: ignore
        InvalidTokenError,
        UserNotFoundError,
        user_service,
    )
except Exception:  # pragma: no cover - tests may inject a stub
    InvalidTokenError = RuntimeError  # type: ignore[assignment]
    UserNotFoundError = RuntimeError  # type: ignore[assignment]
    user_service = None  # type: ignore[assignment]


router = APIRouter(tags=["alerts"])
security = HTTPBearer(auto_error=True)
logger = get_logger(service="alerts_router")
USER_SERVICE_ERROR: dict[str, str] | None = None


class AlertSendPayload(BaseModel):
    message: str
    telegram_chat_id: str | None = None
    discord_channel_id: str | None = None

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El mensaje de la alerta es obligatorio")
        return cleaned


def _serialize_alert(
    alert: Alert, *, prefer_legacy: bool | None = None
) -> dict[str, Any]:
    prefer_legacy = (
        prefer_legacy
        if prefer_legacy is not None
        else bool(getattr(alert, "condition_expression", None))
    )
    value = getattr(alert, "value", None)
    condition_expression = getattr(alert, "condition_expression", None)
    delivery_method = getattr(alert, "delivery_method", None)
    delivery_value = (
        delivery_method.value
        if hasattr(delivery_method, "value")
        else (delivery_method or "push")
    )
    pending_delivery = bool(getattr(alert, "pending_delivery", False))
    name = getattr(alert, "name", None)
    title = getattr(alert, "title", None)
    if name is None and isinstance(title, str):
        name = title

    created_at = getattr(alert, "created_at", None)
    if created_at is not None and not isinstance(created_at, str):
        created_at = created_at.isoformat()
    updated_at = getattr(alert, "updated_at", None)
    if updated_at is not None and not isinstance(updated_at, str):
        updated_at = updated_at.isoformat()

    payload: dict[str, Any] = {
        "id": str(getattr(alert, "id", "")),
        "name": name,
        "title": title or name,
        "asset": getattr(alert, "asset", None),
        "value": float(value) if value is not None else None,
        "active": bool(getattr(alert, "active", False)),
        "delivery_method": delivery_value,
        "pending_delivery": pending_delivery,
        "created_at": created_at,
        "updated_at": updated_at,
        "condition_expression": condition_expression,
        "condition_json": getattr(alert, "condition", None),
    }
    if prefer_legacy:
        legacy_condition = condition_expression
        if legacy_condition is None:
            legacy_condition = getattr(alert, "condition", "")
        payload["condition"] = legacy_condition or ""
    else:
        payload["condition"] = getattr(alert, "condition", None)
    return payload


def _http_exception_from_validation(exc: ValidationError) -> HTTPException:
    errors = exc.errors()
    if errors and all(error.get("type", "") == "value_error" for error in errors):
        message = "; ".join(error.get("msg", str(exc)) for error in errors) or str(exc)
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)

    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    if user_service is None:  # pragma: no cover - dependency not initialised
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User service unavailable",
        )

    token = credentials.credentials
    try:
        return await asyncio.to_thread(user_service.get_current_user, token)
    except InvalidTokenError as exc:  # pragma: no cover - explicit mapping
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def _record_alert_rate_limit(request: Request, action: str) -> None:
    client_ip = request.client.host if request.client else "unknown"
    log_event(
        logger,
        service="alerts_router",
        event="alerts_rate_limited",
        level="warning",
        action=action,
        client_ip=client_ip,
    )
    ALERTS_RATE_LIMITED.labels(action=action).inc()


@router.get("", response_model=list[dict[str, Any]])
async def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    alerts = await asyncio.to_thread(
        alerts_service.list_alerts_for_user, current_user.id
    )
    return [_serialize_alert(alert) for alert in alerts]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: dict[str, Any],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    if isinstance(payload.get("condition"), str):
        try:
            alert_service.validate_condition_expression(payload["condition"])
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        alert_in = AlertCreate.model_validate(payload)
    except ValidationError as exc:
        raise _http_exception_from_validation(exc) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        service_payload = alert_in.to_service_payload()
        alert = await asyncio.to_thread(
            alerts_service.create_alert,
            current_user.id,
            service_payload,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _serialize_alert(alert, prefer_legacy=alert_in.legacy_mode)


@router.put("/{alert_id}")
async def update_alert(
    alert_id: UUID,
    payload: dict[str, Any],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    if isinstance(payload.get("condition"), str):
        try:
            alert_service.validate_condition_expression(payload["condition"])
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        alert_in = AlertUpdate.model_validate(payload)
    except ValidationError as exc:
        raise _http_exception_from_validation(exc) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        service_payload = alert_in.to_service_payload()
        alert = await asyncio.to_thread(
            alerts_service.update_alert,
            current_user.id,
            alert_id,
            service_payload,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _serialize_alert(alert, prefer_legacy=alert_in.legacy_mode)


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        await asyncio.to_thread(alerts_service.delete_alert, current_user.id, alert_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {"message": "Alerta eliminada exitosamente", "id": str(alert_id)}


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_all_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    await asyncio.to_thread(alerts_service.delete_all_alerts_for_user, current_user.id)
    if user_service is not None and hasattr(user_service, "delete_all_alerts_for_user"):
        try:
            await asyncio.to_thread(
                user_service.delete_all_alerts_for_user, current_user.id
            )
        except Exception:  # pragma: no cover - fallback compatibility
            pass
    return {"message": "Todas las alertas fueron eliminadas exitosamente"}


@router.patch("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: UUID,
    payload: AlertToggle,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        alert = await asyncio.to_thread(
            alerts_service.toggle_alert,
            current_user.id,
            alert_id,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _serialize_alert(alert)


@router.post("/send", status_code=status.HTTP_200_OK)
async def send_alert_notification(
    payload: AlertSendPayload,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, dict[str, str]]:
    del current_user  # la autenticación ya validó al usuario
    telegram_chat_id = payload.telegram_chat_id or getattr(
        Config, "TELEGRAM_DEFAULT_CHAT_ID", None
    )
    discord_channel_id = payload.discord_channel_id

    if not telegram_chat_id and not discord_channel_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar un canal de notificación.",
        )

    try:
        return await alert_service.send_external_alert(
            message=payload.message,
            telegram_chat_id=telegram_chat_id,
            discord_channel_id=discord_channel_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# Back-compat para tests: helper interno que los tests llaman directamente
async def _dispatch_alert_rate_limit(request: Request, response: Response) -> None:
    del response  # el helper replica la firma del dependency original
    client_ip = request.client.host if request.client else "testclient"
    try:
        await rate_limiter.record_hit(
            key="alerts:dispatch",
            client_ip=client_ip,
            weight=1,
            detail="Demasiadas solicitudes de envío de alertas",
        )
    except HTTPException:
        _record_alert_rate_limit(request, action="dispatch")
        raise


__all__ = [
    "router",
    "alert_service",
    "alerts_service",
    "USER_SERVICE_ERROR",
    "_record_alert_rate_limit",
    "_dispatch_alert_rate_limit",
]

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


logger = get_logger(service="alerts_router")
router = APIRouter(tags=["alerts"])
security = HTTPBearer(auto_error=True)
USER_SERVICE_ERROR: dict[str, str] | None = None

_REVERSE_CONDITION_OP = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "crosses_above": "crosses_above",
    "crosses_below": "crosses_below",
}


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

    raw_condition = getattr(alert, "condition", None)
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
        "condition_json": raw_condition,
    }
    if prefer_legacy:
        legacy_condition = condition_expression
        if legacy_condition is None:
            legacy_condition = raw_condition
        payload["condition"] = legacy_condition or ""
    else:
        payload["condition"] = raw_condition

    if not prefer_legacy:
        normalized_conditions = _normalize_conditions(raw_condition)
        if normalized_conditions:
            payload["conditions"] = normalized_conditions
    return payload


def _normalize_conditions(condition: Any) -> list[dict[str, Any]] | None:
    if not isinstance(condition, dict):
        return None

    if "and" in condition:
        group = condition["and"]
        if not isinstance(group, list):
            return None
        normalized: list[dict[str, Any]] = []
        for item in group:
            item_conditions = _normalize_conditions(item)
            if not item_conditions:
                return None
            normalized.extend(item_conditions)
        return normalized

    if len(condition) != 1:
        return None

    field, value_map = next(iter(condition.items()))
    if not isinstance(value_map, dict) or len(value_map) != 1:
        return None

    op_key, raw_value = next(iter(value_map.items()))
    op = _REVERSE_CONDITION_OP.get(op_key)
    if op is None:
        return None

    return [
        {
            "field": field,
            "op": op,
            "value": raw_value,
        }
    ]


def _http_exception_from_validation(exc: ValidationError) -> HTTPException:
    errors = exc.errors()
    if errors:
        error_types = {error.get("type", "") for error in errors}
        messages = {error.get("msg", "") for error in errors}
        if any(
            "conditions debe tener al menos 1 condición" in message
            for message in messages
        ):
            return HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="conditions debe tener al menos 1 condición",
            )

        if "float_parsing" in error_types:
            return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

        if all(error_type == "value_error" for error_type in error_types):
            message = "; ".join(messages) or str(exc)
            return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)

    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)


def _http_exception_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    if detail in {
        "conditions debe tener al menos 1 condición",
        "value debe ser numérico",
    }:
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail)


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


async def _ensure_actor(user_id: UUID | None, email: str | None) -> Any:
    if user_service is None:
        return None

    resolved_user: Any | None = None

    if user_id and hasattr(user_service, "get_user_by_id"):
        try:
            resolved_user = await asyncio.to_thread(
                user_service.get_user_by_id, user_id
            )
        except Exception:  # pragma: no cover - compatibility with stubs
            resolved_user = None

    if not resolved_user and email and hasattr(user_service, "get_user_by_email"):
        try:
            resolved_user = await asyncio.to_thread(
                user_service.get_user_by_email, email
            )
        except Exception:  # pragma: no cover - compatibility with stubs
            resolved_user = None

    env = getattr(Config, "ENV", "").lower()
    if not resolved_user and email and env in {"test", "ci"}:
        creator = None
        if hasattr(user_service, "create_user_with_id"):
            creator = user_service.create_user_with_id
            kwargs = {"user_id": user_id, "email": email, "password_hash": "!"}
        elif hasattr(user_service, "create_user"):
            creator = user_service.create_user
            kwargs = {"email": email, "password": "!"}
        else:
            kwargs = {}

        if creator is not None:
            try:
                resolved_user = await asyncio.to_thread(creator, **kwargs)
            except Exception:  # pragma: no cover - compatibility with stubs
                resolved_user = None

        if not resolved_user and hasattr(user_service, "get_user_by_email"):
            try:
                resolved_user = await asyncio.to_thread(
                    user_service.get_user_by_email, email
                )
            except Exception:  # pragma: no cover - last resort
                resolved_user = None

    return resolved_user


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
        raise _http_exception_from_value_error(exc) from exc

    try:
        service_payload = alert_in.to_service_payload()
        actor = await _ensure_actor(
            getattr(current_user, "id", None), getattr(current_user, "email", None)
        )
        actor_id = (
            getattr(actor, "id", None) if actor else getattr(current_user, "id", None)
        )
        if isinstance(actor_id, str):
            try:
                actor_id = UUID(actor_id)
            except ValueError:  # pragma: no cover - defensive conversion
                actor_id = None
        if actor_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="User not found for alert creation",
            )
        alert = await asyncio.to_thread(
            alerts_service.create_alert,
            actor_id,
            service_payload,
            actor_email=getattr(actor, "email", None)
            or getattr(current_user, "email", None),
        )
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise _http_exception_from_value_error(exc) from exc
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if alert_in.legacy_mode and user_service is not None:
        create_alert = getattr(user_service, "create_alert", None)
        if callable(create_alert):
            title = alert_in.title or alert_in.name or service_payload.get("name", "")
            asset = alert_in.asset or service_payload.get("asset") or ""
            try:
                await asyncio.to_thread(
                    create_alert,
                    current_user.id,
                    title=title,
                    asset=asset,
                    value=alert_in.value,
                    condition=alert_in.legacy_operator or ">",
                    active=alert_in.active,
                )
            except Exception as exc:  # pragma: no cover - legacy fallback best-effort
                log_event(
                    logger,
                    service="alerts_router",
                    event="legacy_alert_sync_failed",
                    level="warning",
                    error=str(exc),
                )

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

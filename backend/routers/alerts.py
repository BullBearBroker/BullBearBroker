"""REST endpoints to manage advanced alerts."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.models import User
from backend.schemas.alerts import AlertCreate, AlertOut, AlertToggle
from backend.services.alerts_service import alerts_service

try:  # pragma: no cover - fallback para entornos de pruebas parciales
    from backend.services.user_service import InvalidTokenError, user_service
except Exception:  # pragma: no cover - tests pueden inyectar un stub
    InvalidTokenError = RuntimeError  # type: ignore[assignment]
    user_service = None  # type: ignore[assignment]


router = APIRouter(tags=["alerts"])
security = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    if user_service is None:  # pragma: no cover - dependencias no inicializadas
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User service unavailable")

    token = credentials.credentials
    try:
        return await asyncio.to_thread(user_service.get_current_user, token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("", response_model=list[AlertOut])
async def list_alerts(current_user: Annotated[User, Depends(get_current_user)]) -> list[AlertOut]:
    alerts = await asyncio.to_thread(alerts_service.list_alerts_for_user, current_user.id)
    return [AlertOut.from_model(alert) for alert in alerts]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_in: AlertCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertOut:
    try:
        alert = await asyncio.to_thread(
            alerts_service.create_alert,
            current_user.id,
            alert_in.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AlertOut.from_model(alert)


@router.patch("/{alert_id}/toggle", response_model=AlertOut)
async def toggle_alert(
    alert_id: UUID,
    payload: AlertToggle,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertOut:
    try:
        alert = await asyncio.to_thread(
            alerts_service.toggle_alert,
            current_user.id,
            alert_id,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AlertOut.from_model(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
async def delete_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        await asyncio.to_thread(alerts_service.delete_alert, current_user.id, alert_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "deleted"}

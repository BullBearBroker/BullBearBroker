"""Endpoints for Web Push subscriptions."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import PushSubscription, User
from backend.services.push_service import push_service

try:  # pragma: no cover - optional when running tests without user_service
    from backend.services.user_service import InvalidTokenError, user_service
except Exception:  # pragma: no cover - fallback when user_service is unavailable
    user_service = None  # type: ignore[assignment]
    InvalidTokenError = Exception  # type: ignore[assignment]


router = APIRouter(tags=["push"])
security = HTTPBearer()


class SubscriptionKeys(BaseModel):
    auth: str = Field(..., min_length=4)
    p256dh: str = Field(..., min_length=4)


class PushSubscriptionPayload(BaseModel):
    endpoint: str = Field(..., min_length=10)
    keys: SubscriptionKeys


class PushSubscriptionResponse(BaseModel):
    id: UUID


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    if user_service is None:
        raise HTTPException(status_code=503, detail="Servicio de usuarios no disponible")

    try:
        return await asyncio.to_thread(
            user_service.get_current_user, credentials.credentials
        )
    except InvalidTokenError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/subscribe", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_push(
    payload: PushSubscriptionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PushSubscriptionResponse:
    if user_service is None:
        raise HTTPException(status_code=503, detail="Servicio de usuarios no disponible")

    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )

    if subscription:
        subscription.auth = payload.keys.auth
        subscription.p256dh = payload.keys.p256dh
        subscription.user_id = current_user.id
    else:
        subscription = PushSubscription(
            endpoint=payload.endpoint,
            auth=payload.keys.auth,
            p256dh=payload.keys.p256dh,
            user_id=current_user.id,
        )
        db.add(subscription)

    db.commit()
    db.refresh(subscription)

    return PushSubscriptionResponse(id=subscription.id)


@router.post("/send-test", status_code=status.HTTP_202_ACCEPTED)
async def send_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .all()
    )
    if not subscriptions:
        raise HTTPException(status_code=404, detail="No hay suscripciones registradas")

    payload = {
        "title": "BullBearBroker",
        "body": "Notificación de prueba",
    }

    delivered = push_service.broadcast(subscriptions, payload)
    if delivered == 0:
        raise HTTPException(status_code=502, detail="No se pudieron enviar notificaciones")

    return {"delivered": delivered}

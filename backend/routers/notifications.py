"""Utility endpoints for triggering notifications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import PushSubscription
from backend.services.push_service import push_service

router = APIRouter(prefix="/api/notify", tags=["notifications"])


@router.post("/test", status_code=status.HTTP_202_ACCEPTED)
def send_global_test_notification(db: Session = Depends(get_db)) -> dict[str, int]:
    """Send a broadcast notification to every stored subscription."""

    subscriptions = db.query(PushSubscription).all()
    if not subscriptions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay suscripciones registradas",
        )

    payload = {
        "title": "BullBearBroker",
        "body": "Notificación de prueba global",
    }

    delivered = push_service.broadcast(
        subscriptions,
        payload,
        category="system",
    )

    if delivered == 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron enviar notificaciones",
        )

    return {"delivered": delivered}  # ✅ Codex fix: retorno explícito para evitar warning B008.

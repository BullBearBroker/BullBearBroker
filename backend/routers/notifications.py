# backend/routers/notifications.py

from fastapi import APIRouter, Request, status

from backend.core.config import settings
from backend.schemas.notifications import NotificationEvent  # 🧩 Bloque 9A
from backend.services.audit_service import AuditService

# isort: off
from backend.services.notification_dispatcher import (
    NotificationDispatcher,
    manager,  # 🧩 Bloque 9A
)

# isort: on
from backend.services.push_service import push_service
from backend.services.realtime_service import RealtimeService

# 🧩 Bloque 8A
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# 🧩 Bloque 9A
_LAST_EVENTS: list[NotificationEvent] = []


# 🧩 Bloque 9A
def _append_event(e: NotificationEvent, *, keep: int = 100) -> None:
    _LAST_EVENTS.append(e)
    if len(_LAST_EVENTS) > keep:
        del _LAST_EVENTS[0 : len(_LAST_EVENTS) - keep]


# 🧩 Bloque 9A
@router.get("/logs", response_model=list[NotificationEvent])
def get_recent_logs() -> list[NotificationEvent]:
    # Fallback para polling en el frontend (SWR)
    return _LAST_EVENTS


# 🧩 Bloque 9A
@router.post("/test/broadcast", response_model=NotificationEvent)
async def post_test_broadcast() -> NotificationEvent:
    # Utilidad para QA manual: crea evento y hace broadcast
    e = NotificationEvent(title="Test broadcast", body="Mensaje de prueba (backend)")
    _append_event(e)
    # Como es ruta de prueba, hacemos broadcast directo en el canal WS
    await manager.broadcast(e)
    return e


@router.get("/vapid-key")
def get_vapid_public_key() -> dict[str, str]:
    """Devuelve la clave pública VAPID para el cliente."""
    return {"vapidPublicKey": settings.VAPID_PUBLIC_KEY}


@router.get("/vapid-public-key")
def get_vapid_public_key_legacy() -> dict[str, str]:
    # QA: alias legacy para clientes antiguos.
    return {"vapidPublicKey": settings.VAPID_PUBLIC_KEY}


# 🧩 Codex fix
@router.get("/test", status_code=status.HTTP_200_OK)
def notifications_healthcheck() -> dict[str, str]:
    """Endpoint ligero para pruebas de conectividad."""
    return {"status": "ok"}


# ✅ Servicio de prueba (ya existente)
@router.post("/test", status_code=status.HTTP_202_ACCEPTED)
def send_global_test_notification() -> dict[str, int]:
    """
    Envía una notificación de prueba global a todos los suscriptores push registrados.
    Conserva compatibilidad con el flujo previo de validación.
    """
    subscriptions = push_service.get_all_subscriptions()
    payload = {"title": "BullBearBroker Test", "body": "Prueba de notificación global"}
    sent = push_service.broadcast_to_subscriptions(subscriptions, payload)
    return {"sent": sent}


# ✅ Nuevo endpoint: broadcast manual unificado
@router.post("/broadcast", status_code=status.HTTP_202_ACCEPTED)
async def broadcast_test(request: Request):
    """
    Envía un payload manual a través de todos los canales disponibles:
    - WebSocket (RealtimeService)
    - Web Push (PushService)
    - Audit logs (AuditService)
    """
    payload = await request.json()

    # Instanciar servicios
    realtime = RealtimeService()
    audit = AuditService()
    dispatcher = NotificationDispatcher(
        realtime_service=realtime,
        push_service_channel=push_service,
        audit_service=audit,
    )

    await dispatcher.broadcast_event("manual", payload)
    # 🧩 Bloque 9A
    event = NotificationEvent(
        title=str(payload.get("title") or "Manual broadcast"),
        body=str(payload.get("body") or payload.get("message") or ""),
        meta={"source": "manual-broadcast"},
    )
    _append_event(event)
    await manager.broadcast(event)
    return {"status": "ok", "sent": len(str(payload))}

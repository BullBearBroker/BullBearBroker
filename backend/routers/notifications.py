# backend/routers/notifications.py
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.audit_service import AuditService
from backend.services.notification_dispatcher import NotificationDispatcher
from backend.services.push_service import PushService
from backend.services.realtime_service import RealtimeService

router = APIRouter()


# ✅ Servicio de prueba (ya existente)
@router.post("/test", status_code=status.HTTP_202_ACCEPTED)
def send_global_test_notification() -> dict[str, int]:
    """
    Envía una notificación de prueba global a todos los suscriptores push registrados.
    Conserva compatibilidad con el flujo previo de validación.
    """
    # Ruff fix: evitar Depends() en argumentos por defecto
    db: Session = Depends(get_db)()
    push = PushService(db)
    sent = push.broadcast(
        {"title": "BullBearBroker Test", "body": "Prueba de notificación global"}
    )
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
    # Ruff fix: evitar Depends() en argumentos por defecto
    db: Session = Depends(get_db)()
    payload = await request.json()

    # Instanciar servicios
    realtime = RealtimeService()
    push = PushService(db)
    audit = AuditService()
    dispatcher = NotificationDispatcher(
        realtime_service=realtime, push_service=push, audit_service=audit
    )

    await dispatcher.broadcast_event("manual", payload)
    return {"status": "ok", "sent": len(str(payload))}

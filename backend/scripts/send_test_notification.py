"""Utility script to broadcast a test notification through the dispatcher."""

import asyncio

# QA 2.0: Ejecutar con: APP_ENV=local PYTHONPATH=. .venv/bin/python backend/scripts/send_test_notification.py
# QA 2.0: Verifica que Redis y los canales WebSocket reciban el evento.
from backend.schemas.notifications import (  # CODEx: reutilizamos el esquema oficial de eventos
    NotificationEvent,
)
from backend.services.audit_service import AuditService
from backend.services.notification_dispatcher import (
    NotificationDispatcher,
    PushBroadcastChannel,
)
from backend.services.push_service import push_service
from backend.services.realtime_service import RealtimeService


async def main() -> None:
    dispatcher = NotificationDispatcher(
        realtime_service=RealtimeService(),
        push_service_channel=PushBroadcastChannel(push_service),
        audit_service=AuditService(),
    )

    event = NotificationEvent(
        title="🚀 Notificación de prueba",
        body="Push activo",
        meta={
            "source": "cli",
            "intent": "diagnostic",
        },  # CODEx: metadatos para auditoría
    )
    payload = event.model_dump(
        mode="json"
    )  # CODEx: serializamos con Pydantic para reutilizar validaciones

    await dispatcher.broadcast_event(
        "test_cli", payload
    )  # CODEx: difunde evento estructurado en todos los canales
    print(f"✅ Notificación enviada vía WebSocket y Push (id={event.id})")


if __name__ == "__main__":
    asyncio.run(main())

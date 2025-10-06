"""Utility script to broadcast a test notification through the dispatcher."""

import asyncio
import uuid
from datetime import UTC, datetime

from backend.schemas.notifications import NotificationEvent
from backend.services.audit_service import AuditService
from backend.services.notification_dispatcher import NotificationDispatcher
from backend.services.push_service import push_service
from backend.services.realtime_service import RealtimeService


async def main() -> None:
    dispatcher = NotificationDispatcher(
        realtime_service=RealtimeService(),
        push_service_channel=push_service,
        audit_service=AuditService(),
    )

    event = NotificationEvent(
        id=uuid.uuid4(),
        title="🚀 Notificación de prueba",
        body=f"Emitida a las {datetime.now(UTC).isoformat()}",
        meta={"type": "test"},
    )

    await dispatcher.broadcast_event("test", event.model_dump())
    print("✅ Notificación de prueba enviada vía WebSocket y registrada en logs")


if __name__ == "__main__":
    asyncio.run(main())

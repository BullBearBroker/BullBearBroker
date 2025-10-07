"""Utility script to broadcast a test notification through the dispatcher."""

import asyncio

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

    payload = {
        "title": "🚀 Notificación de prueba",
        "body": "Push activo",
        "type": "test",
    }

    await dispatcher.broadcast_test(payload)
    print("✅ Notificación enviada vía WebSocket y Push")


if __name__ == "__main__":
    asyncio.run(main())

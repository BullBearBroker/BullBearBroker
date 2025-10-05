"""Unified dispatcher to broadcast events across realtime and push channels."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Sequence

from backend.core.logging_config import get_logger
from backend.models.push_subscription import PushSubscription
from backend.services.audit_service import AuditService
from backend.services.push_service import push_service
from backend.services.realtime_service import RealtimeService
from backend.utils.config import ENV

try:  # pragma: no cover - database may be optional in some contexts
    from backend.database import SessionLocal
except Exception:  # pragma: no cover - allow dispatcher to operate without DB
    SessionLocal = None  # type: ignore[assignment]


class PushBroadcastChannel:
    """Asynchronous adapter to deliver payloads using ``PushService``."""

    def __init__(
        self,
        push_service_impl: Any,
        subscription_provider: Callable[[], Awaitable[Sequence[PushSubscription]]] | None = None,
    ) -> None:
        self._service = push_service_impl
        self._subscription_provider = subscription_provider or self._load_subscriptions
        self._logger = get_logger(service="push_broadcast_channel")

    async def _load_subscriptions(self) -> Sequence[PushSubscription]:
        if SessionLocal is None:
            return []

        def _query() -> Sequence[PushSubscription]:
            with SessionLocal() as session:  # type: ignore[misc]
                return session.query(PushSubscription).all()

        return await asyncio.to_thread(_query)

    async def broadcast(self, payload: dict[str, Any]) -> int:
        subscriptions: Sequence[PushSubscription]
        try:
            subscriptions = await self._subscription_provider()
        except Exception as exc:  # pragma: no cover - defensive guard
            self._logger.warning(
                {
                    "service": "push_broadcast_channel",
                    "event": "subscription_fetch_error",
                    "error": str(exc),
                }
            )
            return 0

        if not subscriptions:
            self._logger.info(
                {
                    "service": "push_broadcast_channel",
                    "event": "no_subscriptions",
                }
            )
            return 0

        category = payload.get("category")

        def _send() -> int:
            return self._service.broadcast(subscriptions, payload, category=category)

        try:
            return await asyncio.to_thread(_send)
        except Exception as exc:  # pragma: no cover - ensure dispatcher resilience
            self._logger.warning(
                {
                    "service": "push_broadcast_channel",
                    "event": "broadcast_error",
                    "error": str(exc),
                }
            )
            return 0


class NotificationDispatcher:
    """Dispatch structured events to realtime and push channels."""

    def __init__(
        self,
        realtime_service: RealtimeService,
        push_service_channel: Any,
        audit_service: AuditService,
    ) -> None:
        self.realtime = realtime_service
        self.push = push_service_channel
        self.audit = audit_service
        self._logger = get_logger(service="notification_dispatcher")

    async def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        envelope = self._build_envelope(event_type, payload)
        payload_size = len(json.dumps(envelope.get("payload", {}), default=str))

        self._logger.info(
            {
                "service": "notification_dispatcher",
                "event": "broadcast_start",
                "type": event_type,
                "payload_size": payload_size,
            }
        )

        realtime_status = "skipped"
        try:
            await self.realtime.broadcast(envelope)
            realtime_status = "sent"
        except Exception as exc:  # pragma: no cover - defensive logging
            realtime_status = f"error:{exc}"
            self._logger.warning(
                {
                    "service": "notification_dispatcher",
                    "event": "realtime_error",
                    "type": event_type,
                    "error": str(exc),
                }
            )

        push_status = "skipped"
        try:
            push_result = await self.push.broadcast(envelope)
            push_status = f"sent:{push_result}"
        except Exception as exc:  # pragma: no cover - defensive logging
            push_status = f"error:{exc}"
            self._logger.warning(
                {
                    "service": "notification_dispatcher",
                    "event": "push_error",
                    "type": event_type,
                    "error": str(exc),
                }
            )

        self._logger.info(
            {
                "service": "notification_dispatcher",
                "event": "broadcast_complete",
                "type": event_type,
                "realtime": realtime_status,
                "push": push_status,
                "env": ENV,
            }
        )

        try:
            self.audit.log_event(
                None,
                "notification_sent",
                {"type": event_type, "size": len(str(payload))},
            )
        except Exception:  # pragma: no cover - avoid failing callers on audit issues
            self._logger.warning(
                {
                    "service": "notification_dispatcher",
                    "event": "audit_error",
                    "type": event_type,
                }
            )

    @staticmethod
    def _build_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        summary = payload.get("text") or payload.get("message") or payload.get("body") or ""
        title = payload.get("title") or f"BullBear {event_type.replace('_', ' ').title()}"
        return {
            "type": event_type,
            "title": title,
            "body": summary,
            "payload": payload,
        }


_realtime_service = RealtimeService()
_push_channel = PushBroadcastChannel(push_service)
_audit_service = AuditService()

notification_dispatcher = NotificationDispatcher(
    _realtime_service,
    _push_channel,
    _audit_service,
)


__all__ = ["NotificationDispatcher", "notification_dispatcher"]

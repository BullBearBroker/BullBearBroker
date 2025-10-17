"""Unified dispatcher to broadcast events across realtime and push channels."""

from __future__ import annotations

import asyncio
import inspect  # CODEx: detectar comportamiento síncrono/asíncrono en canales push
import json
from asyncio import Lock  # 🧩 Bloque 9A
from typing import Any  # 🧩 Bloque 9A

from fastapi import WebSocket  # 🧩 Bloque 9A
from redis import asyncio as aioredis  # QA 2.0: cliente Redis asíncrono

from backend.core.logging_config import get_logger
from backend.schemas.notifications import NotificationEvent  # 🧩 Bloque 9A
from backend.services.audit_service import AuditService
from backend.services.push_service import push_service
from backend.services.realtime_service import RealtimeService
from backend.utils.config import ENV, Config  # QA 2.0: obtener REDIS_URL

REDIS_URL = (
    Config.REDIS_URL or "redis://localhost:6379"
)  # QA 2.0: fallback local verificado
redis_client = aioredis.from_url(
    REDIS_URL, decode_responses=True
)  # QA 2.0: conexión compartida


class PushBroadcastChannel:
    """Asynchronous adapter to deliver payloads using ``PushService``."""

    def __init__(self, push_service_impl: Any) -> None:
        self._service = push_service_impl
        self._logger = get_logger(service="push_broadcast_channel")

    async def broadcast(self, payload: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(self._service.broadcast, payload)
        except Exception as exc:  # pragma: no cover - ensure dispatcher resilience
            self._logger.warning(
                {
                    "service": "push_broadcast_channel",
                    "event": "broadcast_error",
                    "error": str(exc),
                }
            )


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
        self.push_service = getattr(
            push_service_channel, "_service", push_service_channel
        )
        self.audit = audit_service
        self._logger = get_logger(service="notification_dispatcher")
        self._logger.info(
            f"🔌 Redis conectado en {REDIS_URL}"
        )  # QA 2.0: verificado conexión configurada

    async def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        envelope = self._build_envelope(event_type, payload)
        payload_size = len(json.dumps(envelope.get("payload", {}), default=str))
        push_payload = self._build_push_payload(event_type, payload, envelope)

        try:
            await redis_client.publish(
                "notifications", json.dumps(envelope, default=str)
            )
            self._logger.info(
                f"📡 Evento publicado en Redis {REDIS_URL}"
            )  # QA 2.0: difusión en canal Redis
        except Exception as exc:  # pragma: no cover - Redis opcional en tests
            self._logger.warning(
                {
                    "service": "notification_dispatcher",
                    "event": "redis_publish_error",
                    "type": event_type,
                    "error": str(exc),
                }
            )

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
        has_keys = getattr(self.push_service, "has_vapid_keys", None)
        if callable(has_keys) and not has_keys():
            self._logger.info(
                {
                    "service": "notification_dispatcher",
                    "event": "push_skipped_missing_keys",
                    "type": event_type,
                }
            )
        else:
            try:
                push_callable = None
                if callable(getattr(self.push, "broadcast", None)):
                    push_callable = self.push.broadcast
                elif callable(getattr(self.push_service, "broadcast", None)):
                    push_callable = self.push_service.broadcast

                if push_callable is None:
                    self._logger.info(
                        {
                            "service": "notification_dispatcher",
                            "event": "push_skipped_missing_callable",
                            "type": event_type,
                        }
                    )
                elif inspect.iscoroutinefunction(
                    push_callable
                ) or asyncio.iscoroutinefunction(push_callable):
                    await push_callable(
                        push_payload
                    )  # CODEx: compatibilidad con canales asíncronos usados en tests
                    push_status = "sent"
                else:
                    await asyncio.to_thread(
                        push_callable, push_payload
                    )  # CODEx: mantener envío síncrono sin bloquear el loop
                    push_status = "sent"
            except Exception as exc:  # pragma: no cover - defensive logging
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

    async def broadcast_test(self, payload: dict[str, Any]) -> None:
        """Helper used by scripts/tests to emit a test notification."""

        await self.broadcast_event("test", payload)

    @staticmethod
    def _build_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        summary = (
            payload.get("text") or payload.get("message") or payload.get("body") or ""
        )
        title = (
            payload.get("title") or f"BullBear {event_type.replace('_', ' ').title()}"
        )
        return {
            "type": event_type,
            "title": title,
            "body": summary,
            "payload": payload,
        }

    @staticmethod
    def _build_push_payload(
        event_type: str, payload: dict[str, Any], envelope: dict[str, Any]
    ) -> dict[str, Any]:
        enriched_payload = dict(payload)
        enriched_payload.setdefault("title", envelope["title"])
        enriched_payload.setdefault("body", envelope["body"])
        enriched_payload.setdefault("type", event_type)
        return enriched_payload


_realtime_service = RealtimeService()
_push_channel = PushBroadcastChannel(push_service)
_audit_service = AuditService()

notification_dispatcher = NotificationDispatcher(
    _realtime_service,
    _push_channel,
    _audit_service,
)


__all__ = [
    "NotificationDispatcher",
    "PushBroadcastChannel",
    "notification_dispatcher",
    "ConnectionManager",  # 🧩 Bloque 9A
    "manager",  # 🧩 Bloque 9A
]


# 🧩 Bloque 9A
class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> set de websockets
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns: set[WebSocket] | None = self.active_connections.get(
                user_id
            )  # 🧩 Bloque 9A
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self.active_connections.pop(user_id, None)

    async def send_personal(self, user_id: str, event: NotificationEvent) -> None:
        payload = json.dumps(event.model_dump(), default=str)
        for ws in list(self.active_connections.get(user_id, set())):
            try:
                await ws.send_text(payload)
            except Exception:
                # Intentar limpiar conexiones muertas
                await self.disconnect(user_id, ws)

    async def broadcast(self, event: NotificationEvent) -> None:
        payload = json.dumps(event.model_dump(), default=str)
        # Copia para evitar mutaciones concurrentes
        all_conns = []
        async with self._lock:
            for conns in self.active_connections.values():
                all_conns.extend(list(conns))
        for ws in all_conns:
            try:
                await ws.send_text(payload)
            except Exception:
                # No conocemos user_id aquí, el WS se limpiará al siguiente intento
                pass


# 🧩 Bloque 9A
manager = ConnectionManager()

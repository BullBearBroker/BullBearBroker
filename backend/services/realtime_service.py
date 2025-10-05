"""Servicio centralizado para gestionar conexiones WebSocket en tiempo real."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from backend.core.logging_config import get_logger, log_event
from backend.metrics.realtime_metrics import (
    ws_connections_active_total,
    ws_errors_total,
    ws_messages_sent_total,
)


class RealtimeService:
    """Administra clientes WebSocket y facilita envíos tipo broadcast."""

    def __init__(self) -> None:
        # ✅ Codex fix: estructura segura para compartir conexiones WebSocket
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._logger = get_logger(service="realtime_service")

    async def register(self, websocket: WebSocket) -> None:
        """Registra una conexión y actualiza métricas de actividad."""

        # ✅ Codex fix: almacenar la conexión aceptada y reflejarla en las métricas
        async with self._lock:
            self._connections.add(websocket)
            ws_connections_active_total.set(len(self._connections))

    async def unregister(self, websocket: WebSocket) -> None:
        """Elimina una conexión y ajusta el recuento de clientes activos."""

        # ✅ Codex fix: eliminar conexiones cerradas y mantener el gauge sincronizado
        async with self._lock:
            self._connections.discard(websocket)
            ws_connections_active_total.set(len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Envía un mensaje a todos los clientes registrados."""

        recipients = await self._snapshot()
        if not recipients:
            return

        preview = self._build_preview(message)
        # ✅ Codex fix: log estructurado de cada broadcast con clientes y mensaje
        self._logger.info({"event": "broadcast", "clients": len(recipients), "message": preview})

        disconnected: list[WebSocket] = []
        for connection in recipients:
            try:
                await connection.send_json(message)
                ws_messages_sent_total.inc()
            except Exception as exc:  # pragma: no cover - resiliencia ante errores inesperados
                ws_errors_total.inc()
                log_event(
                    self._logger,
                    service="realtime_service",
                    event="broadcast_error",
                    level="warning",
                    error=str(exc),
                )
                disconnected.append(connection)

        if disconnected:
            # ✅ Codex fix: retirar conexiones que fallaron durante el envío
            await asyncio.gather(*(self.unregister(connection) for connection in disconnected))

    async def close_all(self) -> None:
        """Cierra todas las conexiones activas (usado en shutdown/tests)."""

        # ✅ Codex fix: cierre ordenado de conexiones en escenarios de apagado
        recipients = await self._snapshot()
        for connection in recipients:
            try:
                await connection.close()
            except Exception:  # pragma: no cover - cierre tolerante a fallos
                ws_errors_total.inc()
        await self._clear_all()

    async def connection_count(self) -> int:
        """Devuelve el número de clientes activos actuales."""

        # ✅ Codex fix: exponer número de conexiones para lógica de difusión periódica
        async with self._lock:
            return len(self._connections)

    async def _snapshot(self) -> list[WebSocket]:
        async with self._lock:
            return list(self._connections)

    async def _clear_all(self) -> None:
        async with self._lock:
            self._connections.clear()
            ws_connections_active_total.set(0)

    @staticmethod
    def _build_preview(message: dict[str, Any]) -> str:
        # ✅ Codex fix: generar un resumen compacto del mensaje para logs
        try:
            serialized = json.dumps(message, ensure_ascii=False)
        except TypeError:
            serialized = str(message)
        return serialized[:200]


__all__ = ["RealtimeService"]

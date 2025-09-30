"""Simple connection manager for alert WebSocket clients."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Set

from fastapi import WebSocket

LOGGER = logging.getLogger(__name__)


class AlertWebSocketManager:
    """Stores active WebSocket connections and broadcasts alert payloads."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def _snapshot(self) -> List[WebSocket]:
        async with self._lock:
            return list(self._connections)

    async def broadcast(self, payload: dict) -> None:
        recipients = await self._snapshot()
        if not recipients:
            return

        for connection in recipients:
            try:
                await connection.send_json(payload)
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.debug("Removing websocket connection after send error: %s", exc)
                await self.disconnect(connection)

    async def close(self) -> None:
        """Close all active connections (used during shutdown/tests)."""
        recipients = await self._snapshot()
        for connection in recipients:
            try:
                await connection.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    async def count(self) -> int:
        async with self._lock:
            return len(self._connections)


__all__ = ["AlertWebSocketManager"]

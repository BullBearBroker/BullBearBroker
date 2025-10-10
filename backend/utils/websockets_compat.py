"""Compat helpers to expose websocket handshake metadata for legacy tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import websockets

if not getattr(
    websockets, "_codex_response_patch", False
):  # CODEx: aplicar una sola vez
    _original_connect = websockets.connect

    class _ConnectWrapper:
        def __init__(self, manager: Any) -> None:
            self._manager = manager

        def __getattr__(self, name: str) -> Any:
            return getattr(self._manager, name)

        def __await__(self):
            async def _await():
                protocol = await self._manager
                _attach_response(protocol)
                return protocol

            return _await().__await__()

        async def __aenter__(self):
            protocol = await self._manager.__aenter__()
            _attach_response(protocol)
            return protocol

        async def __aexit__(self, exc_type, exc, tb):
            return await self._manager.__aexit__(exc_type, exc, tb)

    def _attach_response(protocol: Any) -> None:
        """Ensure the client protocol exposes a handshake response."""

        if getattr(protocol, "response", None) is not None:
            return

        candidate = getattr(protocol, "handshake_response", None)
        if candidate is None:
            candidate = getattr(protocol, "handshake", None)

        status = getattr(candidate, "status", None)
        status_code = getattr(candidate, "status_code", None)
        if status is None and status_code is None:
            status = status_code = 101
        elif status is None:
            status = status_code
        elif status_code is None:
            status_code = status

        protocol.response = SimpleNamespace(
            status=status, status_code=status_code
        )  # CODEx: compatibilidad con pruebas legadas

    def _compat_connect(*args, **kwargs):
        return _ConnectWrapper(_original_connect(*args, **kwargs))

    websockets.connect = _compat_connect  # type: ignore[assignment]
    websockets._codex_response_patch = True

"""Pruebas de integración para el gateway WebSocket de tiempo real."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
import uvicorn
import websockets

from backend.main import app


@pytest_asyncio.fixture()
async def realtime_server(
    unused_tcp_port: int, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[dict[str, str]]:
    """Lanza un servidor Uvicorn para pruebas WebSocket en vivo."""

    # ✅ Codex fix: stub de stream IA para respuestas deterministas durante los tests
    async def fake_stream_generate(_prompt: str):  # noqa: ANN202
        for chunk in ["Insight ", "de prueba"]:
            await asyncio.sleep(0)
            yield chunk

    monkeypatch.setattr(
        "backend.routers.realtime.ai_service.stream_generate",
        fake_stream_generate,
    )

    async def fake_report() -> None:  # ✅ Codex fix: evitar llamadas externas en tests
        return None

    monkeypatch.setattr("backend.main.log_api_integration_report", fake_report)

    port = unused_tcp_port
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
        lifespan="on",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    while not server.started:
        await asyncio.sleep(0.05)

    try:
        yield {"ws": f"ws://127.0.0.1:{port}", "http": f"http://127.0.0.1:{port}"}
    finally:
        server.should_exit = True
        await asyncio.sleep(0)
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_realtime_websocket_connects_and_disconnects(
    realtime_server: dict[str, str],
) -> None:
    """Verifica handshake 101 y mensaje de bienvenida."""

    async with websockets.connect(
        f"{realtime_server['ws']}/api/realtime/ws"
    ) as websocket:
        status = getattr(websocket.response, "status_code", None) or getattr(
            websocket.response, "status", None
        )
        assert status == 101  # ✅ Codex fix: validar handshake Switching Protocols
        initial_raw = await asyncio.wait_for(websocket.recv(), timeout=2)
        initial = json.loads(initial_raw)
        assert initial["status"] == "connected"
        assert "timestamp" in initial

    await asyncio.sleep(0.2)

    async with httpx.AsyncClient() as client:
        metrics = await client.get(realtime_server["http"] + "/api/metrics")
        assert metrics.status_code == 200
        body = metrics.text
        assert "ws_connections_active_total 0.0" in body


@pytest.mark.asyncio
async def test_realtime_streams_prices_and_insights(
    realtime_server: dict[str, str],
) -> None:
    """Recibe precios periódicos y contenidos IA desde el gateway."""

    async with websockets.connect(
        f"{realtime_server['ws']}/api/realtime/ws"
    ) as websocket:
        await websocket.recv()  # mensaje inicial

        price_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=3))
        assert price_message["type"] == "price"
        assert "price" in price_message

        await websocket.send(json.dumps({"action": "subscribe", "channel": "insights"}))
        ack_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
        assert ack_message == {"status": "subscribed", "channel": "insights"}

        insight_message = None
        for _ in range(5):
            candidate = json.loads(await asyncio.wait_for(websocket.recv(), timeout=3))
            if candidate.get("type") == "insight":
                insight_message = candidate
                break
        assert insight_message is not None
        assert "content" in insight_message

        async with httpx.AsyncClient() as client:
            metrics_response = await client.get(
                realtime_server["http"] + "/api/metrics"
            )
        metrics_text = metrics_response.text
        assert "ws_connections_active_total 1.0" in metrics_text
        assert "ws_messages_sent_total" in metrics_text

    await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_realtime_handles_invalid_payload(
    realtime_server: dict[str, str],
) -> None:
    """El gateway responde con error controlado ante cargas inválidas."""

    async with websockets.connect(
        f"{realtime_server['ws']}/api/realtime/ws"
    ) as websocket:
        await websocket.recv()

        await websocket.send("not-json")
        error_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
        assert error_message == {"error": "invalid_payload"}

        await websocket.close()

    await asyncio.sleep(0.1)

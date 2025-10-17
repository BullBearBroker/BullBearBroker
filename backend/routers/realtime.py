"""Gateway WebSocket para difundir precios e insights en tiempo real."""

from __future__ import annotations

import asyncio
import json
import random
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.logging_config import get_logger, log_event
from backend.metrics.realtime_metrics import ws_errors_total, ws_messages_sent_total
from backend.services.ai_service import ai_service
from backend.services.realtime_service import RealtimeService

router = APIRouter()
logger = get_logger(service="realtime_gateway")


async def _ensure_price_task(app) -> None:
    # ✅ Codex fix: arrancar tarea compartida de difusión de precios simulados
    task = getattr(app.state, "realtime_price_task", None)
    if task is None or task.done():
        app.state.realtime_price_task = asyncio.create_task(_price_broadcast_loop(app))


async def _ensure_insights_task(app) -> None:
    # ✅ Codex fix: iniciar tarea de generación de insights IA bajo demanda
    task = getattr(app.state, "realtime_insights_task", None)
    if task is None or task.done():
        app.state.realtime_insights_task = asyncio.create_task(
            _insights_broadcast_loop(app)
        )


async def _price_broadcast_loop(app) -> None:
    service: RealtimeService = app.state.realtime_service
    while True:
        try:
            await asyncio.sleep(1)
            if await service.connection_count() == 0:
                continue
            payload = {
                "type": "price",  # ✅ Codex fix: mensaje estándar de precios simulados
                "symbol": "BBR",
                "price": round(random.uniform(80.0, 120.0), 2),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await service.broadcast(payload)
        except (
            asyncio.CancelledError
        ):  # pragma: no cover - cancelación durante shutdown
            break
        except (
            Exception
        ) as exc:  # pragma: no cover - resiliencia ante errores inesperados
            ws_errors_total.inc()
            log_event(
                logger,
                service="realtime_gateway",
                event="price_loop_error",
                level="warning",
                error=str(exc),
            )


async def _insights_broadcast_loop(app) -> None:
    service: RealtimeService = app.state.realtime_service
    while True:
        try:
            if getattr(app.state, "realtime_insights_subscribers", 0) <= 0:
                await asyncio.sleep(0.5)
                continue

            insight_chunks: list[str] = []
            async for chunk in ai_service.stream_generate(
                "Genera un insight breve del mercado actual"
            ):
                insight_chunks.append(chunk)

            if insight_chunks:
                message = {
                    "type": "insight",  # ✅ Codex fix: difusión de insights IA
                    "content": "".join(insight_chunks).strip(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                await service.broadcast(message)
            await asyncio.sleep(1)
        except (
            asyncio.CancelledError
        ):  # pragma: no cover - cancelación durante shutdown
            break
        except (
            Exception
        ) as exc:  # pragma: no cover - resiliencia ante errores inesperados
            ws_errors_total.inc()
            log_event(
                logger,
                service="realtime_gateway",
                event="insights_loop_error",
                level="warning",
                error=str(exc),
            )
            await asyncio.sleep(1)


def _ensure_state_defaults(app) -> None:
    # ✅ Codex fix: inicializar contadores y tareas compartidas en el estado de la app
    if not hasattr(app.state, "realtime_insights_subscribers"):
        app.state.realtime_insights_subscribers = 0


def _parse_payload(raw_message: str) -> dict[str, Any] | None:
    # ✅ Codex fix: validar y normalizar mensajes entrantes del cliente
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Punto de entrada WebSocket que gestiona suscripciones en tiempo real."""

    await websocket.accept()
    app = websocket.app
    _ensure_state_defaults(app)
    realtime_service: RealtimeService = app.state.realtime_service

    await realtime_service.register(websocket)
    await _ensure_price_task(app)

    initial_message = {
        "status": "connected",  # ✅ Codex fix: saludo inicial con timestamp ISO
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await websocket.send_json(initial_message)
    ws_messages_sent_total.inc()  # ✅ Codex fix: contabilizar saludo inicial enviado

    subscriptions: set[str] = set()

    try:
        while True:
            raw = await websocket.receive_text()
            payload = _parse_payload(raw)
            if not payload:
                ws_errors_total.inc()
                await websocket.send_json({"error": "invalid_payload"})
                ws_messages_sent_total.inc()
                continue

            action = payload.get("action")
            if action == "subscribe":
                channel = payload.get("channel")
                if isinstance(channel, str):
                    subscriptions.add(channel)
                    if channel == "insights":
                        app.state.realtime_insights_subscribers += (
                            1  # ✅ Codex fix: registrar suscriptor a insights
                        )
                        await _ensure_insights_task(app)
                    response = {"status": "subscribed", "channel": channel}
                    await websocket.send_json(response)
                    ws_messages_sent_total.inc()
                else:
                    await websocket.send_json({"error": "invalid_channel"})
                    ws_messages_sent_total.inc()
            elif action == "unsubscribe":
                channel = payload.get("channel")
                if isinstance(channel, str) and channel in subscriptions:
                    subscriptions.remove(channel)
                    if channel == "insights":
                        app.state.realtime_insights_subscribers = max(
                            0,
                            app.state.realtime_insights_subscribers - 1,
                        )  # ✅ Codex fix: ajustar contador de suscriptores activos
                    await websocket.send_json(
                        {"status": "unsubscribed", "channel": channel}
                    )
                    ws_messages_sent_total.inc()
                else:
                    await websocket.send_json({"error": "unknown_subscription"})
                    ws_messages_sent_total.inc()
            elif action == "ping":
                await websocket.send_json({"status": "pong"})
                ws_messages_sent_total.inc()
            else:
                await websocket.send_json({"status": "ack", "received": action})
                ws_messages_sent_total.inc()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - robustez ante fallos no controlados
        ws_errors_total.inc()
        log_event(
            logger,
            service="realtime_gateway",
            event="websocket_error",
            level="warning",
            error=str(exc),
        )
    finally:
        if "insights" in subscriptions and app.state.realtime_insights_subscribers > 0:
            app.state.realtime_insights_subscribers -= 1
        await realtime_service.unregister(websocket)
        if await realtime_service.connection_count() == 0:
            task = getattr(app.state, "realtime_price_task", None)
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                app.state.realtime_price_task = (
                    None  # ✅ Codex fix: liberar referencia a la tarea de precios
                )
        if (
            getattr(app.state, "realtime_insights_subscribers", 0) <= 0
            and getattr(app.state, "realtime_insights_task", None) is not None
        ):
            insights_task = app.state.realtime_insights_task
            insights_task.cancel()
            with suppress(asyncio.CancelledError):
                await insights_task
            app.state.realtime_insights_task = (
                None  # ✅ Codex fix: limpiar tarea de insights inactiva
            )

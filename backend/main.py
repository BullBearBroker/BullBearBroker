import asyncio
import inspect
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from backend.core.logging_config import get_logger
from backend.core.http_logging import RequestLogMiddleware
from backend.core.metrics import MetricsMiddleware, metrics_router
from backend.utils.config import ENV

# Routers de la app
from backend.routers import alerts, markets, news, auth, ai, portfolio, push
from backend.routers import health  # nuevo router de salud
from backend.services.integration_reporter import log_api_integration_report
from backend.services.alert_service import alert_service
from backend.services.websocket_manager import AlertWebSocketManager

try:  # pragma: no cover - user service puede no estar disponible en algunos tests
    from backend.services.user_service import InvalidTokenError, user_service
except Exception:  # pragma: no cover - entorno sin servicio de usuarios
    user_service = None  # type: ignore[assignment]
    InvalidTokenError = Exception  # type: ignore[assignment]

logger = get_logger(service="backend")
logger.info("backend_started")

# ========================
# Lifespan (startup/shutdown)
# ========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    redis_client = None
    db_engine = None
    try:
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await redis_client.ping()
        except Exception as exc:  # pragma: no cover - redis puede no existir
            await redis_client.close()
            redis_client = None
            raise RuntimeError("Redis no disponible") from exc
        await FastAPILimiter.init(redis_client)
        logger.info("fastapi_limiter_initialized")
    except Exception as exc:  # pragma: no cover - redis opcional en tests
        logger.warning("fastapi_limiter_unavailable", error=str(exc))

    try:
        from backend.database import Base, engine as imported_engine
        from backend.services.user_service import user_service

        db_engine = imported_engine
        if ENV == "local":
            Base.metadata.create_all(bind=db_engine)
            logger.info("database_ready")
        else:
            logger.info("database_migrations_required", env=ENV)

        default_email = os.environ.get("BULLBEAR_DEFAULT_USER", "test@bullbear.ai")
        default_password = os.environ.get("BULLBEAR_DEFAULT_PASSWORD", "Test1234!")
        user_service.ensure_user(default_email, default_password)
        logger.info("default_user_ready", email=default_email)
    except Exception as exc:  # pragma: no cover - evita fallas en despliegues sin DB
        logger.error("database_setup_error", error=str(exc))

    try:
        # Informe de integraciones para confirmar que usamos APIs reales.
        await log_api_integration_report()
    except Exception as exc:  # pragma: no cover - logging defensivo
        logger.warning("integration_report_failed", error=str(exc))

    yield  # ⬅️ Aquí FastAPI empieza a servir requests

    # 🔹 Shutdown
    # Si necesitas liberar recursos (ej: cerrar redis) hazlo aquí
    try:
        if "redis_client" in locals() and redis_client:
            await redis_client.aclose()
            FastAPILimiter.redis = None
            logger.info("redis_closed")
    except Exception as exc:
        logger.warning("redis_close_error", error=str(exc))

    try:
        if db_engine is not None:
            dispose_result = db_engine.dispose()
            if inspect.isawaitable(dispose_result):
                await dispose_result
            logger.info("engine_disposed")
    except Exception as exc:
        logger.warning("engine_dispose_error", error=str(exc))


# ========================
# App principal
# ========================
app = FastAPI(
    title="BullBearBroker API",
    version="0.1.0",
    description="🚀 API conversacional para análisis financiero en tiempo real",
    lifespan=lifespan,
)

# Configuración de CORS (controlada por variables de entorno)
raw_origins = os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000")
origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLogMiddleware)

# Endpoint raíz (health básico de la API)
@app.get("/")
def read_root():
    return {"message": "🚀 BullBearBroker API corriendo correctamente!"}


# ✅ Routers registrados con prefijo global /api
app.include_router(metrics_router)
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(auth.router)
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])


alerts_ws_manager = AlertWebSocketManager()
alert_service.register_websocket_manager(alerts_ws_manager)
app.state.alerts_ws_manager = alerts_ws_manager


@app.websocket("/ws/alerts")
async def alerts_websocket(
    websocket: WebSocket, token: str | None = Query(default=None, description="Bearer token opcional")
) -> None:
    """Canal WebSocket que transmite alertas en tiempo real."""

    if token and user_service is not None:
        try:
            await asyncio.to_thread(user_service.get_current_user, token)
        except InvalidTokenError:
            await websocket.close(code=1008, reason="Token inválido")
            return
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.warning("websocket_auth_error", error=str(exc))
            await websocket.close(code=1011, reason="Error autenticando usuario")
            return

    await alerts_ws_manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "system",
                "message": "Conectado al canal de alertas en tiempo real",
            }
        )

        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                message = {"type": "text", "raw": raw_message}

            if isinstance(message, dict) and message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif isinstance(message, dict):
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received": message.get("type", "unknown"),
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - resiliencia ante errores inesperados
        logger.warning("websocket_connection_error", error=str(exc))
    finally:
        await alerts_ws_manager.disconnect(websocket)

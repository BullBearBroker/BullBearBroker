import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from backend.core.logging_config import get_logger, log_event
from backend.core.http_logging import RequestLogMiddleware
from backend.core.metrics import MetricsMiddleware, metrics_router
from backend.core.tracing import configure_tracing
from backend import database as database_module
from backend.models.base import Base
from backend.utils.config import Config, ENV

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

    if getattr(Config, "TESTING", False):
        try:
            from backend.core.rate_limit import clear_testing_state

            await clear_testing_state()
        except Exception:  # pragma: no cover - limpieza defensiva
            pass
        try:
            from backend.core.login_backoff import login_backoff

            await login_backoff.clear_all()
        except Exception:  # pragma: no cover - limpieza defensiva
            pass

    database_setup_failed = False
    database_setup_error_message: str | None = None

    try:
        from backend.services.user_service import user_service

        database_engine = getattr(database_module, "engine", None)
        database_ready = True
        if ENV == "local":
            try:
                if database_engine is None:
                    raise RuntimeError("database engine is not configured")
                Base.metadata.create_all(bind=database_engine, checkfirst=True)
                logger.info("database_ready")
            except Exception as exc:
                database_ready = False
                database_setup_failed = True
                database_setup_error_message = str(exc)
                log_event(
                    logger,
                    service="backend",
                    event="database_setup_error",
                    error=database_setup_error_message,
                )
        else:
            logger.info("database_migrations_required", env=ENV)

        if database_ready:
            default_email = os.environ.get("BULLBEAR_DEFAULT_USER", "test@bullbear.ai")
            default_password = os.environ.get("BULLBEAR_DEFAULT_PASSWORD", "Test1234!")
            user_service.ensure_user(default_email, default_password)
            logger.info("default_user_ready", email=default_email)
    except Exception as exc:  # pragma: no cover - evita fallas en despliegues sin DB
        database_setup_failed = True
        database_setup_error_message = database_setup_error_message or str(exc)
        logger.error("database_setup_error", error=str(exc))
        log_event(
            logger,
            service="backend",
            event="database_setup_error",
            error=database_setup_error_message,
        )

    try:
        # Informe de integraciones para confirmar que usamos APIs reales.
        await log_api_integration_report()
    except Exception as exc:  # pragma: no cover - logging defensivo
        logger.warning("integration_report_failed", error=str(exc))

    yield  # ⬅️ Aquí FastAPI empieza a servir requests

    if database_setup_failed and database_setup_error_message is not None:
        log_event(
            logger,
            service="backend",
            event="database_setup_error",
            error=database_setup_error_message,
        )

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
        current_engine = getattr(database_module, "engine", None)
        if hasattr(current_engine, "dispose") and callable(getattr(current_engine, "dispose", None)):
            current_engine.dispose()
            logger.info("engine_disposed")
        else:
            log_event(
                logger,
                service="backend",
                event="engine_dispose_error",
                error="engine has no dispose()",
            )
    except Exception as exc:
        log_event(
            logger,
            service="backend",
            event="engine_dispose_error",
            error=str(exc),
        )


# ========================
# App principal
# ========================
app = FastAPI(
    title="BullBearBroker API",
    version="0.1.0",
    description="🚀 API conversacional para análisis financiero en tiempo real",
    lifespan=lifespan,
)

try:  # pragma: no cover - tracing may be optional during tests
    configure_tracing(app)
except Exception as exc:  # pragma: no cover - defensive logging
    logger.warning("tracing_configuration_failed", error=str(exc))

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

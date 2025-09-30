import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from backend.core.logging_config import get_logger
from backend.core.http_logging import RequestLogMiddleware

# Routers de la app
from backend.routers import alerts, markets, news, auth, ai, portfolio
from backend.routers import health  # nuevo router de salud
from backend.services.integration_reporter import log_api_integration_report

logger = get_logger()
logger.info("Backend iniciado correctamente 🚀")

# ========================
# Lifespan (startup/shutdown)
# ========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await FastAPILimiter.init(redis_client)
        logger.info("FastAPILimiter inicializado")
    except Exception as exc:  # pragma: no cover - redis opcional en tests
        logger.warning(f"FastAPILimiter no inicializado: {exc}")

    try:
        from backend.database import Base, engine
        from backend.services.user_service import user_service

        Base.metadata.create_all(bind=engine)
        logger.info("Tablas de base de datos verificadas/creadas correctamente")

        default_email = os.getenv("BULLBEAR_DEFAULT_USER", "test@bullbear.ai")
        default_password = os.getenv("BULLBEAR_DEFAULT_PASSWORD", "Test1234!")
        user_service.ensure_user(default_email, default_password)
        logger.info("Usuario por defecto verificado (%s)", default_email)
    except Exception as exc:  # pragma: no cover - evita fallas en despliegues sin DB
        logger.error("Error creando tablas en la base de datos: %s", exc)

    try:
        # Informe de integraciones para confirmar que usamos APIs reales.
        await log_api_integration_report()
    except Exception as exc:  # pragma: no cover - logging defensivo
        logger.warning("No se pudo generar el reporte de integraciones: %s", exc)

    yield  # ⬅️ Aquí FastAPI empieza a servir requests

    # 🔹 Shutdown
    # Si necesitas liberar recursos (ej: cerrar redis) hazlo aquí
    try:
        if "redis_client" in locals() and redis_client:
            await redis_client.close()
            logger.info("Redis cerrado correctamente")
    except Exception as exc:
        logger.warning(f"Error cerrando Redis: {exc}")


# ========================
# App principal
# ========================
app = FastAPI(
    title="BullBearBroker API",
    version="0.1.0",
    description="🚀 API conversacional para análisis financiero en tiempo real",
    lifespan=lifespan,
)

# Configuración de CORS (para el frontend en localhost:3000)
origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

# Endpoint raíz (health básico de la API)
@app.get("/")
def read_root():
    return {"message": "🚀 BullBearBroker API corriendo correctamente!"}


# ✅ Routers registrados con prefijo global /api
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(auth.router)
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])

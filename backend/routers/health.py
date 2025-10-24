import asyncio
import os
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from sqlalchemy import text

from backend import database as database_module
from backend.core.logging_config import get_logger, log_event
from backend.core.rate_limit import rate_limit
from backend.database import get_database_diagnostics
from backend.services.push_service import push_service

# No necesitamos poner prefix aquí, ya lo maneja main.py
router = APIRouter(tags=["health"])
logger = get_logger(service="health_router")
_health_rate_limit = rate_limit(
    times=5,
    seconds=60,
    identifier="health_endpoint",
    detail="Demasiadas consultas al healthcheck. Intenta nuevamente más tarde.",
)


async def _check_redis() -> dict[str, Any]:
    client = getattr(FastAPILimiter, "redis", None)
    if client is None:
        return {"status": "skipped", "detail": "redis_not_configured"}

    try:
        await asyncio.wait_for(client.ping(), timeout=0.5)
    except Exception as exc:  # pragma: no cover - logging defensive
        log_event(
            logger,
            service="health_router",
            event="redis_ping_error",
            level="error",
            error=str(exc),
        )
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok"}


async def _check_database() -> dict[str, Any]:
    engine = getattr(database_module, "engine", None)
    if engine is None:
        details = get_database_diagnostics()
        merged = {
            **details,
            "mode": details.get("mode", "direct"),
            "host": details.get("host", "unknown"),
            "sslmode": details.get("sslmode", "require"),
            "ipv4_forced": details.get("ipv4_forced", False),
        }
        return {
            "status": "skipped",
            "detail": "engine_not_configured",
            "details": merged,
        }

    def _ping() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    diagnostics = get_database_diagnostics()
    enriched = {
        **diagnostics,
        "mode": diagnostics.get(
            "mode",
            (
                "pooler"
                if os.getenv("DB_USE_POOL", "false").lower() == "true"
                else "direct"
            ),
        ),
        "host": diagnostics.get("host", "unknown"),
        "sslmode": diagnostics.get("sslmode", "require"),
        "ipv4_forced": diagnostics.get("ipv4_forced", False),
    }

    try:
        await asyncio.wait_for(asyncio.to_thread(_ping), timeout=3.0)
    except Exception as exc:  # pragma: no cover - logging defensive
        log_event(
            logger,
            service="health_router",
            event="database_ping_error",
            level="error",
            error=str(exc),
        )
        error_message = str(exc)
        hint = None
        lowered = error_message.lower()
        if any(
            keyword in lowered
            for keyword in [
                "name or service not known",
                "could not translate host name",
                "temporary failure in name resolution",
                "network is unreachable",
                "connection timed out",
            ]
        ):
            hint = "Network unreachable/DNS"
        elif "ssl" in lowered:
            hint = "Check Supabase sslmode=require / firewall"

        diagnostic_payload = {
            **enriched,
            "error": error_message[:400],
        }
        if hint:
            diagnostic_payload["hint"] = hint

        return {
            "status": "error",
            "detail": error_message[:200],
            "details": diagnostic_payload,
        }

    return {"status": "ok", "details": enriched}


def _check_push() -> dict[str, Any]:
    # QA: health push visibility – report VAPID configuration without exponer secretos
    try:
        has_keys = push_service.has_vapid_keys()
    except Exception as exc:  # pragma: no cover - defensive
        log_event(
            logger,
            service="health_router",
            event="push_health_error",
            level="error",
            error=str(exc),
        )
        return {
            "status": "error",
            "detail": "push_service_unavailable",
            "details": {"vapid_present": False},
        }

    status = "ok" if has_keys else "warn"
    detail = None if has_keys else "missing_vapid_keys"
    payload: dict[str, Any] = {"status": status, "details": {"vapid_present": has_keys}}
    if detail:
        payload["detail"] = detail
    return payload


@router.get("", dependencies=[Depends(_health_rate_limit)])
@router.get("/", dependencies=[Depends(_health_rate_limit)])
async def health():
    """
    Endpoint básico de salud para monitoreo.
    Devuelve un 'ok' y el entorno actual.
    """
    redis_status = await _check_redis()
    db_status = await _check_database()

    services = {"redis": redis_status, "database": db_status, "push": _check_push()}
    has_errors = any(service["status"] == "error" for service in services.values())
    body = {
        "status": "ok" if not has_errors else "degraded",
        "env": os.getenv("ENV", "unknown"),
        "services": services,
    }

    if has_errors:
        return JSONResponse(status_code=503, content=body)

    return body


@router.get("/ping")
def ping():
    """
    Ruta de diagnóstico sin rate limit.
    Útil para aislar problemas si / devuelve 500.
    """
    return {"pong": True}


@router.get("/version")
def version():
    """
    Endpoint que expone la versión de la API.
    """
    return {"version": "0.1.0"}

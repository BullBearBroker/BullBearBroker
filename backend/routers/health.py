import os
import os
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

# No necesitamos poner prefix aquí, ya lo maneja main.py
router = APIRouter(tags=["health"])

# Fallback simple en memoria si no hay Redis (5 req/60s por IP)
_REQUEST_HISTORY = defaultdict(list)


async def _rate_limit_dependency(request: Request, response: Response):
    """
    Aplica rate limit. Si FastAPILimiter tiene Redis inicializado, usa RateLimiter real.
    Si no, aplica un fallback in-memory por IP (5 req / 60s).
    """
    try:
        # Con Redis disponible: usa el RateLimiter oficial
        if getattr(FastAPILimiter, "redis", None):
            limiter = RateLimiter(times=5, seconds=60)
            # ⬇️ Firma correcta: (request, response)
            return await limiter(request, response)

        # Fallback local sin Redis
        identifier = request.client.host if request.client and request.client.host else "local"
        window = _REQUEST_HISTORY[identifier]
        now = time.monotonic()
        window[:] = [tick for tick in window if now - tick < 60]  # ventana 60s
        if len(window) >= 5:
            raise HTTPException(status_code=429, detail="Too Many Requests")
        window.append(now)
        return
    except HTTPException:
        # Propaga 429 u otros HTTPException
        raise
    except Exception as e:
        # Cualquier error inesperado NO debe romper el endpoint
        raise HTTPException(status_code=500, detail=f"rate_limit_error: {type(e).__name__}") from e


@router.get("", dependencies=[Depends(_rate_limit_dependency)])
@router.get("/", dependencies=[Depends(_rate_limit_dependency)])
async def health():
    """
    Endpoint básico de salud para monitoreo.
    Devuelve un 'ok' y el entorno actual.
    """
    return {
        "status": "ok",
        "env": os.getenv("ENV", "unknown"),
    }


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

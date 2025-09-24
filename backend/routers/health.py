from fastapi import APIRouter, Depends, Request
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import os

# No necesitamos poner prefix aquí, ya lo maneja main.py
router = APIRouter(tags=["health"])


async def _rate_limit_dependency(request: Request):
    if FastAPILimiter.redis is None:  # pragma: no cover - entorno local sin Redis
        return
    limiter = RateLimiter(times=5, seconds=60)
    return await limiter(request)


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


@router.get("/version")
def version():
    """
    Endpoint que expone la versión de la API.
    """
    return {"version": "0.1.0"}

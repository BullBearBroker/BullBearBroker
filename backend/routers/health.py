from fastapi import APIRouter
import os

# No necesitamos poner prefix aquí, ya lo maneja main.py
router = APIRouter(tags=["health"])


@router.get("/")
def health():
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

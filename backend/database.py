"""Database session and Base declarative helpers."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, inspect, text  # [Codex] cambiado - inspección de columnas
from sqlalchemy.orm import sessionmaker

# --- BEGIN PATCH: local auto-create ---
from backend.core.logging_config import get_logger
from backend.models.base import Base
from backend.utils.config import Config, ENV

logger = get_logger(service="database")


def _current_env() -> str:
    # Soporta ambos nombres por compatibilidad
    env = getattr(Config, "ENV", None) or getattr(Config, "ENVIRONMENT", None) or ENV or "prod"
    return str(env).lower()


def create_all_if_local(engine) -> None:
    """Crea las tablas automáticamente sólo en entorno local."""
    env = _current_env()
    if env == "local":
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as exc:  # pragma: no cover - logging manual para depurar entornos sin DB
            logger.error(
                {
                    "service": "database",
                    "event": "database_autocreate_failed",
                    "env": env,
                    "error": str(exc),
                }
            )
        else:
            logger.info(
                {
                    "service": "database",
                    "event": "database_autocreate_executed",
                    "env": env,
                }
            )
    else:
        logger.warning(
            {
                "service": "database",
                "event": "database_autocreate_skipped",
                "env": env,
            }
        )


# --- END PATCH: local auto-create ---

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./bullbearbroker.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine_kwargs = {"future": True, "echo": False, "connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        pool_size=int(getattr(Config, "DB_POOL_SIZE", 5)),
        max_overflow=int(getattr(Config, "DB_MAX_OVERFLOW", 10)),
        pool_recycle=int(getattr(Config, "DB_POOL_RECYCLE", 1800)),
        pool_timeout=int(getattr(Config, "DB_POOL_TIMEOUT", 30)),
    )
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

create_all_if_local(engine)

if _current_env() == "local":
    try:
        inspector = inspect(engine)  # [Codex] nuevo - verificación de columnas adicionales
        if "users" in inspector.get_table_names():
            existing_columns = {col["name"] for col in inspector.get_columns("users")}
            if "risk_profile" not in existing_columns:
                with engine.begin() as connection:
                    connection.execute(
                        text("ALTER TABLE users ADD COLUMN IF NOT EXISTS risk_profile VARCHAR(20)")
                    )
    except Exception as exc:  # pragma: no cover - logging manual para depurar entornos sin DB
        logger.error(
            {
                "service": "database",
                "event": "database_autocreate_column_update_failed",
                "env": _current_env(),
                "error": str(exc),
            }
        )


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]

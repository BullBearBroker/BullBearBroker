"""Database session and Base declarative helpers."""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, inspect, text  # [Codex] cambiado - inspección de columnas
from sqlalchemy.orm import sessionmaker

from backend.core.logging_config import log_event
from backend.models.base import Base
from backend.utils.config import ENV, Config

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

LOGGER = logging.getLogger(__name__)

should_autocreate = (
    ENV == "local"
    and os.environ.get("BULLBEAR_SKIP_AUTOCREATE", "0") != "1"
    and not getattr(Config, "TESTING", False)
)

if should_autocreate:
    try:
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)  # [Codex] nuevo - verificación de columnas adicionales
        if "users" in inspector.get_table_names():
            existing_columns = {col["name"] for col in inspector.get_columns("users")}
            if "risk_profile" not in existing_columns:
                with engine.begin() as connection:
                    connection.execute(
                        text("ALTER TABLE users ADD COLUMN IF NOT EXISTS risk_profile VARCHAR(20)")
                    )
        log_event(LOGGER, service="database", event="database_autocreate_complete", env=ENV)
    except Exception as exc:  # pragma: no cover - logging manual para depurar entornos sin DB
        log_event(
            LOGGER,
            service="database",
            event="database_autocreate_failed",
            level="error",
            error=str(exc),
        )
else:
    log_event(LOGGER, service="database", event="database_autocreate_skipped", env=ENV)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]

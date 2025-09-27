"""Database session and Base declarative helpers."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, inspect, text  # [Codex] cambiado - inspección de columnas
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bullbearbroker.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, future=True, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

if os.getenv("BULLBEAR_SKIP_AUTOCREATE", "0") != "1":
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
    except Exception as exc:  # pragma: no cover - logging manual para depurar entornos sin DB
        import logging

        logging.getLogger(__name__).error("No se pudieron crear las tablas automáticamente: %s", exc)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]

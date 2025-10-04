"""Database session and Base declarative helpers."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.logging_config import get_logger
from backend.models.base import Base
from backend.utils.config import Config

logger = get_logger(service="database")

_TESTING_MODE = bool(getattr(Config, "TESTING", False)) or os.getenv("TESTING", "").lower() in {
    "1",
    "true",
    "on",
    "yes",
}


def _current_env() -> str:
    """Return the active environment name following ENV precedence rules."""

    for env_var in ("ENV", "ENVIRONMENT"):
        value = os.getenv(env_var)
        if value:
            return value
    return "local"


def _resolve_risk_profile_backfill() -> Callable[[object], None] | None:
    """Return the risk profile backfill callable if it exists."""

    # Prefer a function already loaded in the module namespace to avoid re-imports.
    for attr_name in ("run_risk_profile_backfill", "backfill_risk_profiles"):
        candidate = globals().get(attr_name)
        if callable(candidate):
            return candidate  # pragma: no cover - depends on runtime availability

    module_candidates = (
        ("backend.database_backfill", "run_risk_profile_backfill"),
        ("backend.database_backfill", "backfill_risk_profiles"),
        ("backend.migrations.risk_profile_backfill", "run_risk_profile_backfill"),
        ("backend.migrations.risk_profile_backfill", "backfill_risk_profiles"),
    )

    for module_name, attr_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue  # dependencia opcional ausente
        except ImportError:
            continue  # nosec B110: módulo presente pero no usable en este entorno
        except Exception:
            continue  # nosec B110: import inesperado falla; seguimos con el siguiente
        else:
            candidate = getattr(module, attr_name, None)
            if callable(candidate):
                return candidate

    return None


def create_all_if_local(engine) -> None:
    """Create database objects only when running in a local environment."""

    env = _current_env()
    if env != "local":
        logger.warning(
            {
                "service": "database",
                "event": "database_autocreate_skipped",
                "env": env,
                "level": "warning",
            }
        )
        return

    if os.getenv("BULLBEAR_SKIP_AUTOCREATE"):
        logger.info(
            {
                "service": "database",
                "event": "database_autocreate_skipped",
                "env": env,
                "level": "info",
            }
        )
        return

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as error:  # pragma: no cover - defensive logging
        logger.warning(
            {
                "service": "database",
                "event": "database_autocreate_failed",
                "env": "local",
                "error": str(error),
                "level": "warning",
            }
        )
        logger.warning(
            {
                "service": "app",
                "event": "database_setup_error",
                "error": str(error),
                "level": "warning",
            }
        )
        return

    logger.info(
        {
            "service": "database",
            "event": "database_autocreate_executed",
            "env": "local",
            "level": "info",
        }
    )

    backfill = _resolve_risk_profile_backfill()
    if backfill is None:
        return

    try:
        backfill(engine)
    except Exception as error:  # pragma: no cover - logging only
        logger.error(
            {
                "service": "database",
                "event": "risk_profile_migration_failed",
                "env": "local",
                "error": str(error),
                "level": "error",
            }
        )


DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("BULLBEAR_DB_URL") or "sqlite:///./bullbearbroker.db"

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
create_all_if_local(engine)

if _TESTING_MODE and getattr(engine, "dialect", None) is not None:
    try:
        if str(engine.dialect.name).startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
    except Exception as error:  # pragma: no cover - defensive logging for tests
        logger.warning(
            {
                "service": "database",
                "event": "database_autocreate_testing_failed",
                "error": str(error),
                "level": "warning",
            }
        )

_session_factory = globals().get("SessionLocal")
if hasattr(_session_factory, "configure"):
    _session_factory.configure(bind=engine, autocommit=False, autoflush=False, future=True)
    SessionLocal = _session_factory
else:
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]

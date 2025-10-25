"""Database session and Base declarative helpers."""

from __future__ import annotations

import importlib
import os
import threading
from collections.abc import Callable, Generator
from typing import Any, cast
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from backend.core.logging_config import get_logger
from backend.models.base import Base
from backend.utils.config import (
    Config,
    get_database_details,
    get_database_url,
)

logger = get_logger(service="database")

_DATABASE_DETAILS: dict[str, Any] = {}

_TESTING_MODE = bool(getattr(Config, "TESTING", False)) or os.getenv(
    "TESTING", ""
).lower() in {
    "1",
    "true",
    "on",
    "yes",
}

_ENGINE: Engine | None = None
_ENGINE_LOCK = threading.Lock()


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
        except ImportError:
            continue  # nosec B110: dependencia opcional ausente o no usable
        except Exception:  # noqa: BLE001
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
        # QA: create_all only in local
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


def _build_engine_from_env() -> Engine:
    """Build a SQLAlchemy engine honouring Supabase connection rules."""

    database_url = get_database_url()
    if not database_url:
        logger.error(
            {
                "service": "database",
                "event": "database_url_missing",
                "level": "error",
            }
        )
        raise RuntimeError("Database URL not configured")

    use_pool = Config.DB_USE_POOL
    connect_timeout = int(getattr(Config, "DB_CONNECT_TIMEOUT", 10))

    schema_override = os.getenv("TEST_SCHEMA")

    if database_url.startswith("sqlite"):
        engine = cast(
            Engine,
            create_engine(
                database_url,
                future=True,
                echo=False,
                connect_args={"check_same_thread": False},
            ),
        )
        connect_args: dict[str, Any] = {"check_same_thread": False}
    else:
        if use_pool:
            connect_args = {
                "sslmode": "require",
                "prepare_threshold": None,
                "connect_timeout": connect_timeout,
            }
            if schema_override:
                connect_args["options"] = f"-c search_path={schema_override},public"
            pool_size = getattr(Config, "DB_POOL_SIZE", None)
            if pool_size is None:
                pool_size = getattr(Config, "POOL_SIZE", 5)
            max_overflow = getattr(Config, "DB_MAX_OVERFLOW", None)
            if max_overflow is None:
                max_overflow = getattr(Config, "MAX_OVERFLOW", 10)
            pool_timeout = getattr(Config, "DB_POOL_TIMEOUT", None)
            if pool_timeout is None:
                pool_timeout = getattr(Config, "POOL_TIMEOUT", 30)
            pool_recycle = getattr(Config, "DB_POOL_RECYCLE", None)
            if pool_recycle is None:
                pool_recycle = getattr(Config, "POOL_RECYCLE", 1800)
            engine = cast(
                Engine,
                create_engine(
                    database_url,
                    future=True,
                    echo=False,
                    poolclass=QueuePool,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    pool_timeout=pool_timeout,
                    pool_recycle=pool_recycle,
                    pool_pre_ping=True,
                    connect_args=connect_args,
                ),
            )
        else:
            connect_args = {
                "connect_timeout": connect_timeout,
                "prepared_statement_cache_size": 0,
            }
            if schema_override:
                connect_args["options"] = f"-c search_path={schema_override},public"
            pool_size = getattr(Config, "DB_POOL_SIZE", None)
            if pool_size is None:
                pool_size = getattr(Config, "POOL_SIZE", 5)
            max_overflow = getattr(Config, "DB_MAX_OVERFLOW", None)
            if max_overflow is None:
                max_overflow = getattr(Config, "MAX_OVERFLOW", 10)
            pool_timeout = getattr(Config, "DB_POOL_TIMEOUT", None)
            if pool_timeout is None:
                pool_timeout = getattr(Config, "POOL_TIMEOUT", 30)
            pool_recycle = getattr(Config, "DB_POOL_RECYCLE", None)
            if pool_recycle is None:
                pool_recycle = getattr(Config, "POOL_RECYCLE", 1800)
            engine = cast(
                Engine,
                create_engine(
                    database_url,
                    future=True,
                    echo=False,
                    poolclass=QueuePool,
                    pool_size=int(pool_size),
                    max_overflow=int(max_overflow),
                    pool_timeout=int(pool_timeout),
                    pool_recycle=int(pool_recycle),
                    pool_pre_ping=True,
                    connect_args=connect_args,
                ),
            )

    _log_engine_initialization(database_url, connect_args, use_pool)
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

    return engine


def _log_engine_initialization(
    database_url: str, connect_args: dict[str, Any], use_pool: bool
) -> None:
    """Emit a sanitized log containing database connectivity metadata."""

    global _DATABASE_DETAILS

    try:
        details = get_database_details()
        _DATABASE_DETAILS = dict(details)
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning(
            {
                "service": "database",
                "event": "database_details_unavailable",
                "error": str(exc),
                "level": "warning",
            }
        )
        details = {
            "pool": "pgbouncer" if use_pool else "direct",
            "mode": "pooler" if use_pool else "direct",
            "ipv4_forced": False,
        }

    parsed = urlparse(database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (6543 if use_pool else 5432)
    ipv4_forced = bool(details.get("ipv4_forced"))
    mode = details.get("mode", "pooler" if use_pool else "direct")

    prepared_statement_cache_size = (
        connect_args.get("prepared_statement_cache_size") if not use_pool else None
    )

    log_payload = {
        "service": "database",
        "event": "database_engine_initialized",
        "host": host,
        "port": port,
        "pool": details.get("pool", "direct"),
        "mode": mode,
        "sslmode": details.get("sslmode"),
        "connect_timeout": connect_args.get("connect_timeout"),
        "prepared_statement_cache_size": prepared_statement_cache_size,
        "database_ipv4_forced": ipv4_forced,
        "level": "info",
    }
    logger.info(log_payload)
    logger.info(
        "# QA: database_ipv4_forced", extra={"database_ipv4_forced": ipv4_forced}
    )

    _DATABASE_DETAILS.update(
        {
            "host": host,
            "port": port,
            "mode": mode,
            "pool": details.get("pool", "direct"),
            "sslmode": details.get("sslmode"),
            "connect_timeout": connect_args.get("connect_timeout"),
            "ipv4_forced": ipv4_forced,
            "hostaddr": details.get("hostaddr"),
        }
    )


_SESSIONMAKER = sessionmaker(autocommit=False, autoflush=False, future=True)


class _SessionFactoryProxy:
    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def configure(self, **kwargs) -> None:
        self._factory.configure(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._factory, name)

    def __call__(self, *args, **kwargs):
        _ensure_session_bind()
        return self._factory(*args, **kwargs)


SessionLocal = _SessionFactoryProxy(_SESSIONMAKER)


def _ensure_session_bind() -> Engine:
    engine_obj = get_engine()
    _SESSIONMAKER.configure(bind=engine_obj)
    return engine_obj


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine, failing fast on initialization errors."""

    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    with _ENGINE_LOCK:
        if _ENGINE is not None:
            return _ENGINE
        try:
            engine_obj = _build_engine_from_env()
            if hasattr(engine_obj, "connect"):
                with engine_obj.connect() as connection:
                    connection.exec_driver_sql("SELECT 1")
        except Exception as exc:  # pragma: no cover - surfaced to callers/tests
            logger.exception(
                {
                    "service": "database",
                    "event": "engine_init_failed",
                    "error": str(exc),
                }
            )
            raise RuntimeError(f"Engine initialization failed: {exc}") from exc

        _ENGINE = engine_obj
        if hasattr(_SESSIONMAKER, "configure"):
            _SESSIONMAKER.configure(bind=_ENGINE)
        return _ENGINE


# Prime engine on import so dependent modules get a ready-to-use instance.
engine = get_engine()


def reset_engine() -> None:
    """Reset the cached engine, useful for test suites that monkeypatch SQLAlchemy."""

    global _ENGINE
    with _ENGINE_LOCK:
        try:
            if _ENGINE is not None:
                _ENGINE.dispose()
        finally:
            _ENGINE = None
            if hasattr(_SESSIONMAKER, "configure"):
                _SESSIONMAKER.configure(bind=None)


def get_db() -> Generator:
    _ensure_session_bind()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_diagnostics() -> dict[str, Any]:
    """Expose cached database connection metadata for health checks."""

    return dict(_DATABASE_DETAILS)


__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_engine",
    "reset_engine",
    "get_db",
    "get_database_diagnostics",
]

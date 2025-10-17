"""Database session and Base declarative helpers."""

from __future__ import annotations

import importlib
import os
import threading
from collections.abc import Callable, Generator
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from backend.core.logging_config import get_logger
from backend.models.base import Base
from backend.utils.config import Config

logger = get_logger(service="database")

_TESTING_MODE = bool(getattr(Config, "TESTING", False)) or os.getenv(
    "TESTING", ""
).lower() in {
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


def _make_engine() -> Engine:
    """Build a SQLAlchemy engine honouring current pool configuration."""

    database_url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("BULLBEAR_DB_URL")
        or getattr(Config, "DATABASE_URL", "sqlite:///./bullbearbroker.db")
    )

    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine_kwargs: dict[str, Any] = {
        "future": True,
        "echo": False,
        "connect_args": connect_args,
    }

    if not database_url.startswith("sqlite"):
        # QA 2.8: SQLAlchemy pool tuning for PgBouncer (transaction mode)
        pool_size_env = os.getenv("SQLALCHEMY_POOL_SIZE")
        max_overflow_env = os.getenv("SQLALCHEMY_MAX_OVERFLOW")
        pool_recycle_env = os.getenv("SQLALCHEMY_POOL_RECYCLE")
        pool_timeout_env = os.getenv("SQLALCHEMY_POOL_TIMEOUT")
        prefer_env = not os.getenv("PYTEST_CURRENT_TEST")

        if pool_size_env and prefer_env:
            pool_size = int(pool_size_env)
        else:
            pool_size = int(getattr(Config, "DB_POOL_SIZE", 5))

        if max_overflow_env and prefer_env:
            max_overflow = int(max_overflow_env)
        else:
            max_overflow = int(getattr(Config, "DB_MAX_OVERFLOW", 5))

        if pool_recycle_env and prefer_env:
            pool_recycle = int(pool_recycle_env)
        else:
            pool_recycle = int(getattr(Config, "DB_POOL_RECYCLE", 1800))

        if pool_timeout_env and prefer_env:
            pool_timeout = int(pool_timeout_env)
        else:
            pool_timeout = int(getattr(Config, "DB_POOL_TIMEOUT", 30))
        pool_pre_ping = (
            os.getenv(
                "SQLALCHEMY_POOL_PRE_PING",
                "true",
            ).lower()
            == "true"
        )
        engine_kwargs.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_timeout=pool_timeout,
            pool_pre_ping=pool_pre_ping,
        )

    engine = cast(Engine, sa.create_engine(database_url, **engine_kwargs))
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


def _is_valid_engine(obj: Any) -> bool:
    if obj is None:
        return False
    try:
        hash(obj)
    except Exception:
        return False
    return all(
        callable(getattr(obj, attr, None)) for attr in ("dispose", "connect")
    ) and hasattr(getattr(obj, "dialect", None), "name")


_ENGINE_CACHE: Engine | None = None
_ENGINE_LOCK = threading.Lock()

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
    if not _is_valid_engine(engine_obj):
        with _ENGINE_LOCK:
            engine_obj = _make_engine()
            if not _is_valid_engine(engine_obj):
                raise RuntimeError("Engine not available (invalid stub detected)")
            global _ENGINE_CACHE
            _ENGINE_CACHE = cast(Engine, engine_obj)
    _SESSIONMAKER.configure(bind=cast(Engine, engine_obj))
    return cast(Engine, engine_obj)


def get_engine() -> Engine | Any:
    """Return a cached SQLAlchemy engine, rebuilding if the cache is invalid."""

    global _ENGINE_CACHE
    with _ENGINE_LOCK:
        if _ENGINE_CACHE is not None and _is_valid_engine(_ENGINE_CACHE):
            return _ENGINE_CACHE

        candidate = _make_engine()
        if _is_valid_engine(candidate):
            _ENGINE_CACHE = cast(Engine, candidate)
            _SESSIONMAKER.configure(bind=_ENGINE_CACHE)
            return _ENGINE_CACHE

        return candidate


class _EngineProxy:
    def __getattr__(self, name: str) -> Any:
        engine_obj = get_engine()
        if not _is_valid_engine(engine_obj):
            with _ENGINE_LOCK:
                real_engine = _make_engine()
                if not _is_valid_engine(real_engine):
                    raise RuntimeError("Engine not available (invalid stub detected)")
                global _ENGINE_CACHE
                _ENGINE_CACHE = cast(Engine, real_engine)
                engine_obj = _ENGINE_CACHE
        return getattr(engine_obj, name)


engine = _EngineProxy()


def _initialize_engine_cache() -> None:
    """Prime the engine cache on import so tests can capture create_engine kwargs."""

    global _ENGINE_CACHE
    try:
        candidate = _make_engine()
    except Exception:
        return

    if _is_valid_engine(candidate):
        with _ENGINE_LOCK:
            _ENGINE_CACHE = cast(Engine, candidate)
            _SESSIONMAKER.configure(bind=_ENGINE_CACHE)


_initialize_engine_cache()


def reset_engine() -> None:
    """Reset the cached engine, useful for test suites that monkeypatch SQLAlchemy."""

    global _ENGINE_CACHE
    with _ENGINE_LOCK:
        try:
            if _ENGINE_CACHE is not None and _is_valid_engine(_ENGINE_CACHE):
                _ENGINE_CACHE.dispose()
        finally:
            _ENGINE_CACHE = None
            _SESSIONMAKER.configure(bind=None)


def get_db() -> Generator:
    _ensure_session_bind()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_engine", "reset_engine", "get_db"]

import asyncio
import logging
import os
import time
from secrets import token_urlsafe
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv
from passlib.context import CryptContext

from backend.core.config import settings as core_settings

load_dotenv()

LOGGER = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    """Wrapper around :func:`os.environ.get` that trims whitespace."""

    value = os.environ.get(name, default)
    if isinstance(value, str):
        value = value.strip() or None
    return value


def _get_int_env(name: str, default: int) -> int:
    """Return an integer environment variable with graceful fallback."""

    raw_value = _get_env(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        LOGGER.warning("Invalid int for %s: %s", name, raw_value)
        return default


def _require_env(name: str) -> str:
    """Return an environment variable or raise a descriptive error."""

    value = _get_env(name)
    if value is None:
        LOGGER.error("Missing required environment variable %s", name)
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = _get_env(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


_SUPPORTED_ENVIRONMENTS = {"local", "staging", "production"}

_ENVIRONMENT_DEFAULTS = {
    # 🧩 Codex fix: valores por defecto seguros por entorno
    "local": {
        "DATABASE_URL": "sqlite+aiosqlite:///./app.db",  # pragma: allowlist secret
        "SUPABASE_URL": "http://localhost:54321",
        "SUPABASE_KEY": "local_supabase_key",
    },
    "staging": {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/bullbearbroker",  # pragma: allowlist secret
        "SUPABASE_URL": "https://staging.supabase.co",
        "SUPABASE_KEY": "staging_supabase_key",
    },
    "production": {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/bullbearbroker",  # pragma: allowlist secret
        "SUPABASE_URL": "https://api.supabase.prod",
        "SUPABASE_KEY": "production_supabase_key",
    },
}

APP_ENV = (_get_env("APP_ENV", "local") or "local").lower()
if APP_ENV not in _SUPPORTED_ENVIRONMENTS:
    LOGGER.warning("unknown_app_env", extra={"app_env": APP_ENV})
    APP_ENV = "local"

# 🧩 Codex fix: mantener compatibilidad con ENV pero priorizar APP_ENV
ENV = _get_env("ENV") or APP_ENV

_active_defaults = _ENVIRONMENT_DEFAULTS[APP_ENV]


class Config:
    APP_ENV = APP_ENV  # 🧩 Codex fix: exponer entorno activo
    ENV = ENV
    DATABASE_URL = _get_env("DATABASE_URL") or _active_defaults["DATABASE_URL"]
    SUPABASE_URL = _get_env("SUPABASE_URL") or _active_defaults["SUPABASE_URL"]
    SUPABASE_KEY = _get_env("SUPABASE_KEY") or _active_defaults["SUPABASE_KEY"]
    # Stocks APIs
    ALPHA_VANTAGE_API_KEY = _get_env("ALPHA_VANTAGE_API_KEY")
    TWELVEDATA_API_KEY = _get_env("TWELVEDATA_API_KEY")

    # Crypto APIs
    COINMARKETCAP_API_KEY = _get_env("COINMARKETCAP_API_KEY")

    # Redis cache
    REDIS_URL = _get_env(
        "REDIS_URL", "redis://localhost:6379"
    )  # QA 2.0: verificado fallback local

    # News APIs
    NEWSAPI_API_KEY = _get_env("NEWSAPI_API_KEY")
    CRYPTOPANIC_API_KEY = _get_env("CRYPTOPANIC_API_KEY")
    FINFEED_API_KEY = _get_env("FINFEED_API_KEY")

    # AI providers
    MISTRAL_API_KEY = _get_env("MISTRAL_API_KEY")
    HUGGINGFACE_API_KEY = _get_env("HUGGINGFACE_API_KEY") or _get_env(
        "HUGGINGFACE_API_TOKEN"
    )
    HUGGINGFACE_MODEL = _get_env(
        "HUGGINGFACE_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct"
    )
    HUGGINGFACE_SENTIMENT_MODEL = _get_env(
        "HUGGINGFACE_SENTIMENT_MODEL",
        "distilbert-base-uncased-finetuned-sst-2-english",
    )
    HUGGINGFACE_API_URL = _get_env(
        "HUGGINGFACE_API_URL", "https://api-inference.huggingface.co/models"
    )
    OLLAMA_HOST = _get_env("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = _get_env("OLLAMA_MODEL", "llama3")
    AI_DECORATE_MARKET = True

    # Authentication / security
    JWT_SECRET_KEY = _get_env("BULLBEARBROKER_SECRET_KEY") or token_urlsafe(64)
    JWT_ALGORITHM = _get_env("BULLBEARBROKER_JWT_ALGORITHM", "HS256")
    TESTING = _get_bool_env("TESTING", False)

    _LOGIN_IP_DEFAULT_REQUESTS = _get_int_env("LOGIN_IP_LIMIT_TIMES", 20)
    _LOGIN_IP_DEFAULT_WINDOW = _get_int_env("LOGIN_IP_LIMIT_SECONDS", 60)
    LOGIN_IP_LIMIT_REQUESTS = _get_int_env(
        "LOGIN_IP_LIMIT_REQUESTS", _LOGIN_IP_DEFAULT_REQUESTS
    )
    LOGIN_IP_LIMIT_WINDOW_SECONDS = _get_int_env(
        "LOGIN_IP_LIMIT_WINDOW_SECONDS", _LOGIN_IP_DEFAULT_WINDOW
    )
    LOGIN_BACKOFF_START_AFTER = _get_int_env("LOGIN_BACKOFF_START_AFTER", 3)
    if TESTING:
        LOGIN_IP_LIMIT_REQUESTS = (
            20  # 🧩 Codex fix: mantener límites realistas en tests
        )
        LOGIN_IP_LIMIT_WINDOW_SECONDS = 60
    LOGIN_IP_LIMIT_TIMES = LOGIN_IP_LIMIT_REQUESTS
    LOGIN_IP_LIMIT_SECONDS = LOGIN_IP_LIMIT_WINDOW_SECONDS

    ENABLE_CAPTCHA_ON_LOGIN = _get_bool_env("ENABLE_CAPTCHA_ON_LOGIN", False)
    LOGIN_CAPTCHA_THRESHOLD = _get_int_env("LOGIN_CAPTCHA_THRESHOLD", 3)
    LOGIN_CAPTCHA_TEST_SECRET = _get_env("LOGIN_CAPTCHA_TEST_SECRET", "pass")
    LOGIN_SOFT_LOCK_THRESHOLD = _get_int_env("LOGIN_SOFT_LOCK_THRESHOLD", 5)
    LOGIN_SOFT_LOCK_COOLDOWN = _get_int_env("LOGIN_SOFT_LOCK_COOLDOWN", 900)

    MAX_CONCURRENT_SESSIONS = _get_int_env("MAX_CONCURRENT_SESSIONS", 5)

    ENABLE_PASSWORD_BREACH_CHECK = _get_bool_env("ENABLE_PASSWORD_BREACH_CHECK", False)
    PASSWORD_BREACH_DATASET_PATH = _get_env("PASSWORD_BREACH_DATASET_PATH")

    # Notifications
    TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN")
    TELEGRAM_DEFAULT_CHAT_ID = _get_env("TELEGRAM_DEFAULT_CHAT_ID")
    DISCORD_BOT_TOKEN = _get_env("DISCORD_BOT_TOKEN")
    DISCORD_APPLICATION_ID = _get_env("DISCORD_APPLICATION_ID")
    PUSH_VAPID_PUBLIC_KEY = _get_env("PUSH_VAPID_PUBLIC_KEY") or getattr(
        core_settings, "VAPID_PUBLIC_KEY", None
    )
    PUSH_VAPID_PRIVATE_KEY = _get_env("PUSH_VAPID_PRIVATE_KEY") or getattr(
        core_settings, "VAPID_PRIVATE_KEY", None
    )
    PUSH_CONTACT_EMAIL = _get_env("PUSH_CONTACT_EMAIL", "support@bullbear.ai")

    API_BASE_URL = _get_env(
        "BULLBEAR_API_URL", "http://localhost:8000"
    )  # [Codex] nuevo

    ENABLE_TRACING = _get_bool_env("ENABLE_TRACING", False)
    OTEL_SERVICE_NAME = _get_env("OTEL_SERVICE_NAME", "bullbearbroker-backend")
    OTEL_EXPORTER_OTLP_ENDPOINT = _get_env("OTEL_EXPORTER_OTLP_ENDPOINT")
    OTEL_EXPORTER_OTLP_HEADERS = _get_env("OTEL_EXPORTER_OTLP_HEADERS")
    OTEL_EXPORTER_OTLP_TIMEOUT = _get_int_env("OTEL_EXPORTER_OTLP_TIMEOUT", 10)

    DB_POOL_SIZE = _get_int_env("DB_POOL_SIZE", 5)
    DB_MAX_OVERFLOW = _get_int_env("DB_MAX_OVERFLOW", 10)
    DB_POOL_RECYCLE = _get_int_env("DB_POOL_RECYCLE", 1800)
    DB_POOL_TIMEOUT = _get_int_env("DB_POOL_TIMEOUT", 30)
    _FOREX_FALLBACK_RAW = _get_env("FOREX_FALLBACK_ORDER")
    if _FOREX_FALLBACK_RAW:
        FOREX_FALLBACK_ORDER = [
            item.strip() for item in _FOREX_FALLBACK_RAW.split(",") if item.strip()
        ]
    else:
        FOREX_FALLBACK_ORDER = ["Twelve Data", "Yahoo Finance"]

    HTTPX_TIMEOUT_TIMESERIES = _get_int_env("HTTPX_TIMEOUT_TIMESERIES", 15)
    HTTPX_CONNECT_TIMEOUT_TIMESERIES = _get_int_env(
        "HTTPX_CONNECT_TIMEOUT_TIMESERIES", 10
    )

    require_env = staticmethod(_require_env)


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class _InMemoryAsyncRedis:
    """Minimal async-compatible Redis-like client for tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            payload = self._store.get(key)
            if not payload:
                return None
            value, expires_at = payload
            if expires_at is not None and expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        async with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._store[key] = (value, expires_at)


_redis_instance: redis.Redis | None = None
_fallback_redis = _InMemoryAsyncRedis()


def get_redis() -> Any:
    """Return a Redis client or a shared in-memory fallback for tests."""

    global _redis_instance

    if _redis_instance is not None:
        return _redis_instance

    redis_url = Config.REDIS_URL or "redis://localhost:6379"
    try:
        _redis_instance = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        return _redis_instance
    except Exception as exc:  # pragma: no cover - logged for observability
        LOGGER.warning("redis_client_init_failed", extra={"error": str(exc)})

    return _fallback_redis

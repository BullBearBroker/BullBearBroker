import logging
import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import dotenv_values, load_dotenv
from passlib.context import CryptContext

_ORIGINAL_ENV = dict(os.environ)
_BACKEND_DIR = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
PLACEHOLDER_HOSTS = {"hostname.supabase.co", "hostname.supabase.com"}
_LAST_CONNECTION_DETAILS: dict[str, Any] = (
    {}
)  # QA: last DB connection details for health

# QA: password hashing context (singleton) — kept for backwards compatibility
password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def _load_backend_env_files() -> None:
    """Apply backend env files with explicit precedence and compatibility notes."""

    # QA: env precedence – process > .env.local > .env.staging/.env.production
    # QA: do not load .env.example in runtime; examples are documentation-only
    raw_hint = _ORIGINAL_ENV.get("APP_ENV") or os.getenv("APP_ENV")
    app_env_hint: str | None
    if raw_hint:
        app_env_hint = raw_hint.strip().lower()
    else:
        app_env_hint = None
        for probe in (".env.local", ".env.production", ".env.staging"):
            probe_path = _BACKEND_DIR / probe
            if not probe_path.exists():
                continue
            probe_values = dotenv_values(probe_path)
            hinted = probe_values.get("APP_ENV")
            if hinted:
                app_env_hint = hinted.strip().lower()
                break
        if app_env_hint is None:
            app_env_hint = "staging"

    if app_env_hint in {"prod", "production"}:
        app_env_hint = "production"
    elif app_env_hint in {"stage", "staging"}:
        app_env_hint = "staging"
    elif app_env_hint in {"local", "dev", "development"}:
        app_env_hint = "local"

    candidate_files: list[Path] = []
    base_env = _BACKEND_DIR / ".env"
    if base_env.exists():
        candidate_files.append(base_env)
    if app_env_hint == "production":
        candidate_files.extend(
            [
                _BACKEND_DIR / ".env.production",
                _BACKEND_DIR / ".env.production.local",
            ]
        )
    elif app_env_hint == "staging":
        candidate_files.extend(
            [
                _BACKEND_DIR / ".env.staging",
                _BACKEND_DIR / ".env.staging.local",
            ]
        )

    for path in candidate_files:
        if path.exists():
            load_dotenv(path, override=False)

    local_override = _BACKEND_DIR / ".env.local"
    if local_override.exists():
        local_values = dotenv_values(local_override)
        for key, value in local_values.items():
            if value is None:
                continue
            if key in _ORIGINAL_ENV:
                continue
            os.environ[key] = value


_load_backend_env_files()


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if isinstance(value, str):
        value = value.strip() or None
    return value


def _get_int_env(name: str, default: int) -> int:
    raw_value = _get_env(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        LOGGER.warning("invalid_int_env", extra={"name": name, "value": raw_value})
        return default


def _require_env(name: str) -> str:
    value = _get_env(name)
    if value is None:
        LOGGER.error("Missing required environment variable: %s", name)
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_bool(key: str, default: bool = False) -> bool:
    raw_value = _get_env(key)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw_value = os.getenv(key)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except Exception:
        LOGGER.warning("invalid_int_env", extra={"name": key, "value": raw_value})
        return default


def _get_bool_env(name: str, default: bool = False) -> bool:
    return _env_bool(name, default)


def _force_ipv4_hostaddr(url: str) -> tuple[str, bool, str | None]:
    parsed = urlparse(url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return url, False, None

    if "hostaddr" in query_items:
        return url, True, query_items["hostaddr"]

    if hostname in {item.lower() for item in PLACEHOLDER_HOSTS}:
        LOGGER.warning(
            "# QA: placeholder host detected; use db.<project_ref>.supabase.co."
        )
        return url, False, None

    if not hostname.endswith(".supabase.co"):
        return url, False, None

    port = parsed.port or 5432

    try:
        infos = socket.getaddrinfo(hostname, port, family=socket.AF_INET)
    except socket.gaierror as exc:  # pragma: no cover
        LOGGER.warning(
            "supabase_ipv4_resolution_failed",
            extra={"host": hostname, "port": port, "error": str(exc)},
        )
        return url, False, None

    if not infos:
        LOGGER.warning(
            "supabase_ipv4_resolution_empty",
            extra={"host": hostname, "port": port},
        )
        return url, False, None

    ipv4 = infos[0][4][0]
    query_items["hostaddr"] = ipv4
    new_query = urlencode(query_items)
    updated = parsed._replace(query=new_query)
    return urlunparse(updated), True, ipv4


def force_ipv4_hostaddr(url: str) -> tuple[str, bool, str | None]:
    return _force_ipv4_hostaddr(url)


_SUPPORTED_ENVIRONMENTS = {"local", "staging", "production"}

_ENVIRONMENT_DEFAULTS = {
    "local": {
        "DATABASE_URL": "sqlite+aiosqlite:///./app.db",
        "SUPABASE_URL": "http://localhost:54321",
        "SUPABASE_KEY": "local_supabase_key",
    },
    "staging": {
        "DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/bullbearbroker",
        "SUPABASE_URL": "https://staging.supabase.co",
        "SUPABASE_KEY": "staging_supabase_key",
    },
    "production": {
        "DATABASE_URL": "postgresql+psycopg://user:pass@host:5432/bullbearbroker",
        "SUPABASE_URL": "https://api.supabase.prod",
        "SUPABASE_KEY": "production_supabase_key",
    },
}

APP_ENV = (_get_env("APP_ENV", "local") or "local").lower()
if APP_ENV not in _SUPPORTED_ENVIRONMENTS:
    LOGGER.warning("unknown_app_env", extra={"app_env": APP_ENV})
    APP_ENV = "local"

ENV = _get_env("ENV") or APP_ENV

_active_defaults = _ENVIRONMENT_DEFAULTS[APP_ENV]


def _normalize_postgres_scheme(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _ensure_query_params(url: str, connect_timeout: int) -> str:
    parsed = urlparse(url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_items.setdefault("sslmode", "require")
    query_items.setdefault("connect_timeout", str(connect_timeout))
    normalized = parsed._replace(query=urlencode(query_items))
    return urlunparse(normalized)


def _record_connection_details(
    *,
    driver: str,
    mode: str,
    host: str,
    port: int | None,
    sslmode: str,
    connect_timeout: int,
    ipv4_forced: bool,
    hostaddr: str | None,
) -> None:
    global _LAST_CONNECTION_DETAILS
    _LAST_CONNECTION_DETAILS = {
        "driver": driver,
        "mode": mode,
        "pool": "pgbouncer" if mode == "pooler" else "direct",
        "host": host,
        "port": port,
        "sslmode": sslmode,
        "connect_timeout": connect_timeout,
        "ipv4_forced": ipv4_forced,
        "hostaddr": hostaddr,
    }


def get_database_url() -> str:
    connect_timeout = _get_int_env("DB_CONNECT_TIMEOUT", 10)
    use_pool = _get_bool_env("DB_USE_POOL", False)

    pool_url = _get_env("SUPABASE_DB_POOL_URL")
    direct_url = _get_env("SUPABASE_DB_URL")
    fallback_url = _get_env("DATABASE_URL") or _active_defaults["DATABASE_URL"]

    if use_pool:
        selected = pool_url or direct_url or fallback_url
    else:
        if pool_url:
            LOGGER.warning("# QA: DB_USE_POOL=false – ignoring SUPABASE_DB_POOL_URL")
        if _get_env("DATABASE_URL"):
            LOGGER.warning("# QA: DB_USE_POOL=false – ignoring DATABASE_URL fallback")
        selected = direct_url or fallback_url

    if selected.startswith("sqlite"):
        _record_connection_details(
            driver="sqlite",
            mode="direct",
            host="local",
            port=None,
            sslmode="",
            connect_timeout=connect_timeout,
            ipv4_forced=False,
            hostaddr=None,
        )
        return selected

    normalized = _ensure_query_params(
        _normalize_postgres_scheme(selected), connect_timeout
    )
    ipv4_forced = False
    resolved_ipv4: str | None = None

    hostaddr_override = _get_env("SUPABASE_DB_HOSTADDR")

    if not use_pool:
        if hostaddr_override:
            parsed_override = urlparse(normalized)
            query_items_override = dict(
                parse_qsl(parsed_override.query, keep_blank_values=True)
            )
            if query_items_override.get("hostaddr") != hostaddr_override:
                query_items_override["hostaddr"] = hostaddr_override
                normalized = urlunparse(
                    parsed_override._replace(query=urlencode(query_items_override))
                )
            ipv4_forced = True
            resolved_ipv4 = hostaddr_override
            LOGGER.info(
                "# QA: database_ipv4_forced via SUPABASE_DB_HOSTADDR",
                extra={"database_ipv4_forced": True},
            )
            if direct_url:
                os.environ["SUPABASE_DB_URL"] = normalized
        else:
            normalized, ipv4_forced, resolved_ipv4 = _force_ipv4_hostaddr(normalized)
            if ipv4_forced and direct_url:
                os.environ["SUPABASE_DB_URL"] = normalized
        # QA: hostaddr override or auto-resolution applied

    parsed = urlparse(normalized)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    mode = "pooler" if use_pool and pool_url else "direct"
    _record_connection_details(
        driver="psycopg" if normalized.startswith("postgresql+") else parsed.scheme,
        mode=mode,
        host=parsed.hostname or "localhost",
        port=parsed.port,
        sslmode=query_items.get("sslmode", "require"),
        connect_timeout=int(query_items.get("connect_timeout", connect_timeout)),
        ipv4_forced=ipv4_forced or "hostaddr" in query_items,
        hostaddr=query_items.get("hostaddr") or resolved_ipv4,
    )
    if not use_pool:
        LOGGER.info(
            "# QA: database_ipv4_forced",
            extra={
                "database_ipv4_forced": bool(
                    query_items.get("hostaddr") or resolved_ipv4
                )
            },
        )

    return normalized


def get_database_details() -> dict[str, Any]:
    if not _LAST_CONNECTION_DETAILS:
        get_database_url()
    return dict(_LAST_CONNECTION_DETAILS)


class Config:
    APP_ENV = APP_ENV
    ENV = ENV
    SUPABASE_DB_URL = _get_env("SUPABASE_DB_URL")
    SUPABASE_DB_POOL_URL = _get_env("SUPABASE_DB_POOL_URL")
    DB_CONNECT_TIMEOUT = _get_int_env("DB_CONNECT_TIMEOUT", 10)
    DB_USE_POOL = _env_bool("DB_USE_POOL", False)
    REDIS_URL = _get_env("REDIS_URL") or "redis://localhost:6379/0"
    ENABLE_CAPTCHA_ON_LOGIN = _env_bool("ENABLE_CAPTCHA_ON_LOGIN", False)
    LOGIN_CAPTCHA_TEST_SECRET = _get_env("LOGIN_CAPTCHA_TEST_SECRET")
    NEWSAPI_API_KEY = _get_env("NEWSAPI_API_KEY")
    MEDIASTACK_API_KEY = _get_env("MEDIASTACK_API_KEY")
    TWELVEDATA_API_KEY = _get_env("TWELVEDATA_API_KEY")
    ALPHA_VANTAGE_API_KEY = _get_env("ALPHA_VANTAGE_API_KEY")
    COINMARKETCAP_API_KEY = _get_env("COINMARKETCAP_API_KEY")
    CRYPTOPANIC_API_KEY = _get_env("CRYPTOPANIC_API_KEY")
    FINFEED_API_KEY = _get_env("FINFEED_API_KEY")
    TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN")
    TELEGRAM_DEFAULT_CHAT_ID = _get_env("TELEGRAM_DEFAULT_CHAT_ID")
    DISCORD_BOT_TOKEN = _get_env("DISCORD_BOT_TOKEN")
    DISCORD_APPLICATION_ID = _get_env("DISCORD_APPLICATION_ID")
    PASSWORD_BREACH_DATASET_PATH = _get_env("PASSWORD_BREACH_DATASET_PATH")
    ENABLE_PASSWORD_BREACH_CHECK = _env_bool("ENABLE_PASSWORD_BREACH_CHECK", False)
    HTTPX_TIMEOUT_TIMESERIES = _env_int("HTTPX_TIMEOUT_TIMESERIES", 10)
    JWT_SECRET_KEY = _get_env("JWT_SECRET") or _get_env("JWT_SECRET_KEY") or "change_me"
    JWT_ALGORITHM = _get_env("JWT_ALGORITHM", "HS256")
    MAX_CONCURRENT_SESSIONS = _env_int("MAX_CONCURRENT_SESSIONS", 5)
    HUGGINGFACE_API_KEY = _get_env("HUGGINGFACE_API_KEY")
    HUGGINGFACE_API_URL = (
        _get_env("HUGGINGFACE_API_URL") or "https://api-inference.huggingface.co"
    )
    HUGGINGFACE_SENTIMENT_MODEL = (
        _get_env("HUGGINGFACE_SENTIMENT_MODEL")
        or "siebert/sentiment-roberta-large-english"
    )
    HUGGINGFACE_MODEL = _get_env("HUGGINGFACE_MODEL")
    HUGGINGFACE_RISK_MODELS = _get_env("HUGGINGFACE_RISK_MODELS")
    AI_DECORATE_MARKET = _env_bool("AI_DECORATE_MARKET", True)
    API_BASE_URL = _get_env("API_BASE_URL") or "http://127.0.0.1:8000"
    OLLAMA_HOST = _get_env("OLLAMA_HOST")
    OLLAMA_MODEL = _get_env("OLLAMA_MODEL")
    TESTING = _env_bool("TESTING", False)
    POOL_SIZE = _env_int("DB_POOL_SIZE", 5)
    MAX_OVERFLOW = _env_int("DB_MAX_OVERFLOW", 10)
    POOL_TIMEOUT = _env_int("DB_POOL_TIMEOUT", 30)
    POOL_RECYCLE = _env_int("DB_POOL_RECYCLE", 1800)

    @classmethod
    def require_env(
        cls,
        name: str,
        *,
        aliases: tuple[str, ...] | list[str] = (),
        default: str | None = None,
        optional: bool = False,
    ) -> str:
        """
        Helper to enforce presence of environment variables with optional alias/default.
        """

        candidates = [name, *(aliases or ())]
        for candidate in candidates:
            value = os.getenv(candidate)
            if value is not None:
                return value

        if default is not None:
            return default

        if optional:
            return ""

        LOGGER.error("Missing required environment variable: %s", name)
        raise KeyError(name)

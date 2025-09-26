import logging
import os
from secrets import token_urlsafe
from typing import Optional

from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

LOGGER = logging.getLogger(__name__)


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Wrapper around :func:`os.getenv` that trims whitespace."""

    value = os.getenv(name, default)
    if isinstance(value, str):
        value = value.strip() or None
    return value


def _require_env(name: str) -> str:
    """Return an environment variable or raise a descriptive error."""

    value = _get_env(name)
    if value is None:
        LOGGER.error("Missing required environment variable %s", name)
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Config:
    # Stocks APIs
    ALPHA_VANTAGE_API_KEY = _get_env("ALPHA_VANTAGE_API_KEY")
    TWELVEDATA_API_KEY = _get_env("TWELVEDATA_API_KEY")

    # Crypto APIs
    COINMARKETCAP_API_KEY = _get_env("COINMARKETCAP_API_KEY")

    # Redis cache
    REDIS_URL = _get_env("REDIS_URL")

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

    # Authentication / security
    JWT_SECRET_KEY = _get_env("BULLBEARBROKER_SECRET_KEY") or token_urlsafe(64)
    JWT_ALGORITHM = _get_env("BULLBEARBROKER_JWT_ALGORITHM", "HS256")

    # Notifications
    TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN")
    TELEGRAM_DEFAULT_CHAT_ID = _get_env("TELEGRAM_DEFAULT_CHAT_ID")
    DISCORD_BOT_TOKEN = _get_env("DISCORD_BOT_TOKEN")
    DISCORD_APPLICATION_ID = _get_env("DISCORD_APPLICATION_ID")

    require_env = staticmethod(_require_env)


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

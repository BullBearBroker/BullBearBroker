"""Core configuration helpers for BullBearBroker backend."""

import os


class Settings:
    """Centralized access to environment-driven configuration values."""

    APP_ENV: str = os.getenv("APP_ENV", "local")
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "")


settings = Settings()

# Backwards compatibility for modules that import module-level constants.
VAPID_PUBLIC_KEY = settings.VAPID_PUBLIC_KEY
VAPID_PRIVATE_KEY = settings.VAPID_PRIVATE_KEY

if settings.APP_ENV == "local" and not settings.VAPID_PUBLIC_KEY:
    print("⚠️ Warning: VAPID_PUBLIC_KEY not set in environment.")

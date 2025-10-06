"""Utilities to register and deliver Web Push notifications."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - optional dependency in some environments
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - provide graceful fallback for tests

    class WebPushException(Exception):
        """Raised when pywebpush is unavailable."""

    def webpush(**_: Any) -> None:  # type: ignore
        raise WebPushException("pywebpush package is not installed")


# 🧩 Codex fix
from backend.core import config as core_config
from backend.models.push_preference import PushNotificationPreference
from backend.models.push_subscription import PushSubscription
from backend.utils.config import Config

LOGGER = logging.getLogger(__name__)


class PushService:
    """Encapsulates Web Push subscription handling and delivery."""

    def __init__(
        self,
        *,
        vapid_private_key: str | None = None,
        vapid_public_key: str | None = None,
        contact_email: str | None = None,
        vapid_claims: dict[str, Any] | str | None = None,
    ) -> None:
        env_vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        env_vapid_public_key = os.getenv("VAPID_PUBLIC_KEY") or os.getenv(
            "PUSH_VAPID_PUBLIC_KEY"
        )
        try:
            env_vapid_claims = json.loads(
                os.getenv("VAPID_CLAIMS", "{}")
            )  # ✅ Codex fix: cargamos las claims VAPID estandarizadas desde el entorno.
        except json.JSONDecodeError:
            LOGGER.warning("Invalid JSON for VAPID_CLAIMS", exc_info=True)
            env_vapid_claims = None

        config_private_key = (
            getattr(Config, "PUSH_VAPID_PRIVATE_KEY", None)
            or getattr(Config, "VAPID_PRIVATE_KEY", None)
            or getattr(core_config, "VAPID_PRIVATE_KEY", None)
        )  # 🧩 Codex fix: normalizamos la clave privada entre Config y core.config
        config_public_key = (
            getattr(Config, "PUSH_VAPID_PUBLIC_KEY", None)
            or getattr(Config, "VAPID_PUBLIC_KEY", None)
            or getattr(core_config, "VAPID_PUBLIC_KEY", None)
        )  # 🧩 Codex fix: normalizamos la clave pública entre Config y core.config
        config_claims = getattr(Config, "PUSH_VAPID_CLAIMS", None)  # 🧩 Codex fix

        self._vapid_private_key = (
            vapid_private_key or env_vapid_private_key or config_private_key
        )  # ✅ Codex fix: priorizamos la variable de entorno final VAPID_PRIVATE_KEY.
        self._vapid_public_key = (
            vapid_public_key or env_vapid_public_key or config_public_key
        )  # ✅ Codex fix: priorizamos la variable de entorno final VAPID_PUBLIC_KEY.
        self._contact_email = contact_email or Config.PUSH_CONTACT_EMAIL
        self._vapid_claims = self._parse_claims(
            vapid_claims or env_vapid_claims or config_claims
        )  # ✅ Codex fix: compatibilidad con claims definidas tanto en JSON como en Config.

    @property
    def is_configured(self) -> bool:
        return bool(self._vapid_private_key and self._vapid_public_key)

    def _parse_claims(
        self, claims: dict[str, Any] | str | None
    ) -> dict[str, Any] | None:
        if isinstance(claims, dict):
            return claims
        if isinstance(claims, str) and claims:
            try:
                parsed = json.loads(claims)
            except json.JSONDecodeError:
                LOGGER.warning("Invalid JSON for VAPID_CLAIMS: %s", claims)
            else:
                if isinstance(parsed, dict):
                    return parsed
                LOGGER.warning("VAPID_CLAIMS must decode to a JSON object: %s", claims)
        return None

    def _build_claims(self) -> dict[str, Any]:
        if self._vapid_claims:
            return self._vapid_claims
        contact = self._contact_email or "support@bullbear.ai"
        if not contact.startswith("mailto:"):
            contact = f"mailto:{contact}"
        return {"sub": contact}

    def send_notification(
        self, subscription: PushSubscription, payload: dict[str, Any]
    ) -> None:
        if not self.is_configured:
            raise RuntimeError("Web Push configuration missing VAPID keys")

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"auth": subscription.auth, "p256dh": subscription.p256dh},
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self._vapid_private_key,
                vapid_public_key=self._vapid_public_key,
                vapid_claims=self._build_claims(),
            )
        except WebPushException as exc:  # pragma: no cover - defensive logging
            LOGGER.warning("Web push delivery failed: %s", exc)
            raise RuntimeError("Failed to deliver push notification") from exc

    def _is_category_allowed(
        self, subscription: PushSubscription, category: str | None
    ) -> bool:
        if category is None:
            return True

        user = getattr(subscription, "user", None)
        preferences: PushNotificationPreference | None = None
        if user is not None:
            preferences = getattr(user, "push_preferences", None)

        if preferences is None:
            return True

        mapping = {
            "alerts": preferences.alerts_enabled,
            "news": preferences.news_enabled,
            "system": preferences.system_enabled,
        }
        return mapping.get(category, True)

    def broadcast(
        self,
        subscriptions: Iterable[PushSubscription],
        payload: dict[str, Any],
        *,
        category: str | None = None,
    ) -> int:
        delivered = 0
        for subscription in subscriptions:
            if not self._is_category_allowed(subscription, category):
                continue
            try:
                self.send_notification(subscription, payload)
            except RuntimeError:
                continue
            delivered += 1
        return delivered


push_service = PushService()

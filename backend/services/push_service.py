"""Utilities to register and deliver Web Push notifications."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - optional dependency in some environments
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - provide graceful fallback for tests
    class WebPushException(Exception):
        """Raised when pywebpush is unavailable."""

    def webpush(**_: Any) -> None:  # type: ignore
        raise WebPushException("pywebpush package is not installed")

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
    ) -> None:
        self._vapid_private_key = vapid_private_key or Config.PUSH_VAPID_PRIVATE_KEY
        self._vapid_public_key = vapid_public_key or Config.PUSH_VAPID_PUBLIC_KEY
        self._contact_email = contact_email or Config.PUSH_CONTACT_EMAIL

    @property
    def is_configured(self) -> bool:
        return bool(self._vapid_private_key and self._vapid_public_key)

    def _build_claims(self) -> dict[str, str]:
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

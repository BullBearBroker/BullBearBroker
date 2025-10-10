"""Utilities to register and deliver Web Push notifications."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

from pywebpush import WebPushException, webpush

from backend.core.config import settings
from backend.models.push_preference import PushNotificationPreference
from backend.models.push_subscription import PushSubscription

try:  # pragma: no cover - database may be optional in some contexts
    from backend.database import SessionLocal
except Exception:  # pragma: no cover - allow operating without a database
    SessionLocal = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


class PushService:
    """Encapsulates Web Push subscription handling and delivery."""

    def __init__(self) -> None:
        self.logger = LOGGER
        # These attributes remain for backwards compatibility with existing tests
        self._vapid_private_key: str | None = None
        self._vapid_public_key: str | None = None

    def get_all_subscriptions(self) -> list[PushSubscription]:
        """Return every stored subscription, if a database is available."""

        if SessionLocal is None:
            return []

        with SessionLocal() as session:  # type: ignore[misc]
            return session.query(PushSubscription).all()

    def _resolve_vapid_keys(
        self,
        *,
        override_private: str | None = None,
        override_public: str | None = None,
    ) -> tuple[str | None, str | None]:
        vapid_private = (
            override_private or settings.VAPID_PRIVATE_KEY or self._vapid_private_key
        )
        vapid_public = (
            override_public or settings.VAPID_PUBLIC_KEY or self._vapid_public_key
        )
        return vapid_private, vapid_public

    def has_vapid_keys(self) -> bool:
        """Return ``True`` when both VAPID keys are available."""

        vapid_private, vapid_public = self._resolve_vapid_keys()
        return bool(vapid_private and vapid_public)

    def _deliver(
        self,
        subscription: PushSubscription,
        payload: dict[str, Any],
        *,
        vapid_private: str,
        vapid_public: str,
    ) -> bool:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"auth": subscription.auth, "p256dh": subscription.p256dh},
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_private,
                vapid_public_key=vapid_public,
                vapid_claims={"sub": "mailto:admin@bullbear.ai"},
            )
        except WebPushException as exc:  # pragma: no cover - defensive logging
            self.logger.warning(f"Push failed for {subscription.endpoint}: {exc}")
            return False
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.warning(
                "Unexpected error delivering web push for %s: %s",
                subscription.endpoint,
                exc,
            )
            return False

        return True

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

    def broadcast_to_subscriptions(
        self,
        subscriptions: Iterable[PushSubscription],
        payload: dict[str, Any],
        *,
        category: str | None = None,
    ) -> int:
        """Send ``payload`` to the provided subscriptions."""

        vapid_private, vapid_public = self._resolve_vapid_keys()
        if not vapid_public or not vapid_private:
            self.logger.warning("VAPID keys missing — skipping push")
            return 0

        delivered = 0
        for subscription in subscriptions:
            if not self._is_category_allowed(subscription, category):
                continue
            if self._deliver(
                subscription,
                payload,
                vapid_private=vapid_private,
                vapid_public=vapid_public,
            ):
                delivered += 1

        return delivered

    def broadcast(
        self,
        payload_or_subscriptions: dict[str, Any] | Iterable[PushSubscription],
        maybe_payload: dict[str, Any] | None = None,
        *,
        category: str | None = None,
    ) -> int:
        """
        Send ``payload`` to subscriptions, optionally providing a pre-filtered iterable.

        - ``broadcast(payload)`` preserves el comportamiento previo.
        - ``broadcast(subscriptions, payload, category=...)`` permite a servicios como
          alerts_service reutilizar la misma ruta manteniendo compatibilidad con los tests.
        """

        if isinstance(payload_or_subscriptions, dict):
            payload = payload_or_subscriptions
            subscriptions: Iterable[PushSubscription] | None = None
        else:
            subscriptions = list(payload_or_subscriptions)
            payload = maybe_payload or {}

        vapid_private = settings.VAPID_PRIVATE_KEY or self._vapid_private_key
        vapid_public = settings.VAPID_PUBLIC_KEY or self._vapid_public_key
        if not vapid_public or not vapid_private:
            self.logger.warning("VAPID keys missing — skipping push")
            return 0

        target_subscriptions = (
            list(subscriptions)
            if subscriptions is not None
            else self.get_all_subscriptions()
        )
        if not target_subscriptions:
            return 0

        effective_category = category
        if effective_category is None and isinstance(payload, dict):
            effective_category = payload.get("category")

        return self.broadcast_to_subscriptions(
            target_subscriptions,
            payload,
            category=effective_category,
        )  # CODEx: reutilizamos la lógica central respetando filtros por categoría


push_service = PushService()

"""Utilities to register and deliver Web Push notifications."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pywebpush import WebPushException, webpush

from backend.core.config import settings
from backend.models.push_preference import PushNotificationPreference
from backend.models.push_subscription import PushSubscription


# QA: resolver SessionLocal dinámicamente para convivir con recargas en tests/xDIST
def _get_session_factory():  # pragma: no cover - helper invoked en tiempo de ejecución
    try:
        from backend import database as database_module

        return getattr(database_module, "SessionLocal", None)
    except Exception:
        return None


LOGGER = logging.getLogger(__name__)


def endpoint_fingerprint(endpoint: str) -> str:
    """Return a stable, privacy-safe fingerprint for logging."""

    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:12]


# QA: utilidades para pruning y expiración
PRUNE_FAIL_THRESHOLD = 5
PRUNE_GRACE_HOURS = 24


class PushService:
    """Encapsulates Web Push subscription handling and delivery."""

    def __init__(self) -> None:
        self.logger = LOGGER
        # These attributes remain for backwards compatibility with existing tests
        self._vapid_private_key: str | None = None
        self._vapid_public_key: str | None = None
        self._vapid_subject: str | None = getattr(settings, "VAPID_SUBJECT", None)
        if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
            self.logger.warning(
                "VAPID keys missing at startup – push delivery degraded until configured"
            )  # QA: advertencia temprana cuando faltan claves
        if not self._vapid_subject:
            self.logger.debug(
                "VAPID subject missing – default mailto placeholder will be used"
            )

    def get_all_subscriptions(self) -> list[PushSubscription]:
        """Return every stored subscription, if a database is available."""

        session_factory = _get_session_factory()
        if session_factory is None:
            return []

        with session_factory() as session:  # type: ignore[misc]
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

    def _build_vapid_claims(self) -> dict[str, str]:
        # QA: permite configurar el subject VAPID vía entorno.
        subject = getattr(settings, "VAPID_SUBJECT", None) or self._vapid_subject
        if not subject:
            subject = "mailto:soporte@bullbearbroker.example"
        return {"sub": subject}

    def has_vapid_keys(self) -> bool:
        """Return ``True`` when both VAPID keys are available."""

        vapid_private, vapid_public = self._resolve_vapid_keys()
        return bool(vapid_private and vapid_public)

    def _mark_delivery_failure(self, subscription_id, *, mark_pruning: bool) -> None:
        session_factory = _get_session_factory()
        if session_factory is None:
            return

        with session_factory() as session:  # type: ignore[misc]
            record = session.get(PushSubscription, subscription_id)
            if record is None:
                return
            raw_failures = record.fail_count or 0
            try:
                current_failures = int(raw_failures) + 1
            except (TypeError, ValueError):
                current_failures = 1
            record.fail_count = current_failures
            record.last_fail_at = datetime.now(UTC)
            if mark_pruning:
                record.pruning_marked = True
            session.commit()

    def _reset_subscription_state(self, subscription_id) -> None:
        session_factory = _get_session_factory()
        if session_factory is None:
            return

        with session_factory() as session:  # type: ignore[misc]
            record = session.get(PushSubscription, subscription_id)
            if record is None:
                return
            record.fail_count = 0
            record.last_fail_at = None
            record.pruning_marked = False
            session.commit()

    @staticmethod
    def should_prune_subscription(
        subscription: PushSubscription, reference: datetime | None = None
    ) -> bool:
        """Determine if a subscription should be pruned based on failure history."""

        pruning_marked = getattr(subscription, "pruning_marked", False)
        if isinstance(pruning_marked, str):
            pruning_marked = pruning_marked.lower() == "true"
        if pruning_marked:
            return True

        raw_fail_count = getattr(subscription, "fail_count", 0) or 0
        try:
            fail_count = int(raw_fail_count)
        except (TypeError, ValueError):
            fail_count = 0
        if fail_count < PRUNE_FAIL_THRESHOLD:
            return False

        last_fail_at = getattr(subscription, "last_fail_at", None)
        if last_fail_at is None:
            return False

        if last_fail_at.tzinfo is None:
            last_fail_at = last_fail_at.replace(tzinfo=UTC)

        reference_ts = reference or datetime.now(UTC)
        return last_fail_at <= reference_ts - timedelta(hours=PRUNE_GRACE_HOURS)

    def _send_with_retries(
        self,
        subscription: PushSubscription,
        payload: dict[str, Any],
        *,
        vapid_private: str,
        vapid_public: str,
    ) -> bool:
        fingerprint = endpoint_fingerprint(subscription.endpoint)
        attempts = 0

        while True:
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
                    vapid_claims=self._build_vapid_claims(),
                )
            except WebPushException as exc:  # pragma: no cover - defensive logging
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                mark_pruning = status_code in {404, 410}
                message = getattr(response, "text", "") or str(exc)
                reason = message.strip().replace("\n", " ")[:160]
                self._mark_delivery_failure(subscription.id, mark_pruning=mark_pruning)
                self.logger.warning(
                    "webpush_error endpoint=%s status=%s attempt=%s pruning=%s reason=%s",
                    fingerprint,
                    status_code or "unknown",
                    attempts + 1,
                    mark_pruning,
                    reason,
                )
                if mark_pruning:
                    break

                schedule: list[float] = []
                if status_code == 429:
                    schedule = [0.5, 1.0, 2.0, 4.0]
                elif status_code is not None and 500 <= status_code < 600:
                    schedule = [0.5, 1.5]
                else:
                    break

                if attempts >= 3 or attempts >= len(schedule):
                    break

                time.sleep(schedule[attempts])
                attempts += 1
                continue
            except Exception as exc:  # pragma: no cover - defensive logging
                self._mark_delivery_failure(subscription.id, mark_pruning=False)
                self.logger.warning(
                    "webpush_exception endpoint=%s attempt=%s error=%s",
                    fingerprint,
                    attempts + 1,
                    str(exc)[:160],
                )
                break
            else:
                self._reset_subscription_state(subscription.id)
                self.logger.debug(
                    "webpush_delivered endpoint=%s attempts=%s",
                    fingerprint,
                    attempts + 1,
                )
                return True

            break

        return False

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
            session_factory = _get_session_factory()
            if session_factory is not None:
                with session_factory() as session:
                    preferences = (
                        session.query(PushNotificationPreference)
                        .filter(
                            PushNotificationPreference.user_id
                            == getattr(subscription, "user_id", None)
                        )
                        .one_or_none()
                    )

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
            if self.should_prune_subscription(subscription):
                self.logger.debug(
                    "skip_pruned_subscription endpoint=%s",
                    endpoint_fingerprint(subscription.endpoint),
                )
                continue
            if not self._is_category_allowed(subscription, category):
                continue
            if self._send_with_retries(
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

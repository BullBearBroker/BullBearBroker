from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from backend.models.push_subscription import PushSubscription
from backend.services.push_service import (
    PRUNE_FAIL_THRESHOLD,
    PRUNE_GRACE_HOURS,
    endpoint_fingerprint,
    push_service,
)


def _subscription() -> PushSubscription:
    return PushSubscription(
        endpoint="https://example.com/push/1",
        auth="auth",
        p256dh="p256dh",
        user_id=uuid.uuid4(),
    )


def test_endpoint_fingerprint_deterministic() -> None:
    fingerprint = endpoint_fingerprint("https://example.com/test")
    assert len(fingerprint) == 12
    assert fingerprint == endpoint_fingerprint("https://example.com/test")
    assert fingerprint != endpoint_fingerprint("https://example.com/other")


def test_should_prune_subscription_by_mark() -> None:
    subscription = _subscription()
    subscription.pruning_marked = True
    assert push_service.should_prune_subscription(subscription)


def test_should_prune_subscription_by_fail_count_and_age() -> None:
    subscription = _subscription()
    subscription.fail_count = PRUNE_FAIL_THRESHOLD
    subscription.last_fail_at = datetime.now(UTC) - timedelta(hours=PRUNE_GRACE_HOURS + 1)
    assert push_service.should_prune_subscription(subscription)


def test_not_prune_when_recent_failure() -> None:
    subscription = _subscription()
    subscription.fail_count = PRUNE_FAIL_THRESHOLD + 1
    subscription.last_fail_at = datetime.now(UTC)
    assert not push_service.should_prune_subscription(subscription)

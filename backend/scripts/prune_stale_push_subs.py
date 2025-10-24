#!/usr/bin/env python
# QA: pruning policy – elimina suscripciones Web Push inválidas o inactivas

"""CLI helper to prune stale Web Push subscriptions based on failure metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from backend.models.push_subscription import PushSubscription
from backend.services.push_service import (
    PRUNE_FAIL_THRESHOLD,
    PRUNE_GRACE_HOURS,
    endpoint_fingerprint,
    push_service,
)


def main() -> None:
    session_factory = None
    try:
        from backend import database as database_module

        session_factory = getattr(database_module, "SessionLocal", None)
    except Exception:  # pragma: no cover - defensive
        session_factory = None

    if session_factory is None:
        print(
            json.dumps(
                {
                    "deleted": 0,
                    "kept": 0,
                    "detail": "session_factory_unavailable",
                }
            )
        )
        return

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=PRUNE_GRACE_HOURS)

    delete_fingerprints: list[str] = []
    keep_count = 0
    delete_ids: list = []

    with session_factory() as session:  # type: ignore[misc]
        candidates = session.query(PushSubscription).all()

        for subscription in candidates:
            should_delete = push_service.should_prune_subscription(
                subscription, reference=now
            )
            if not should_delete:
                # Grace period for repeated failures without mark
                fail_count = getattr(subscription, "fail_count", 0) or 0
                last_fail = getattr(subscription, "last_fail_at", None)
                if (
                    fail_count >= PRUNE_FAIL_THRESHOLD
                    and last_fail is not None
                    and (
                        last_fail if last_fail.tzinfo else last_fail.replace(tzinfo=UTC)
                    )
                    <= cutoff
                ):
                    should_delete = True

            if should_delete:
                delete_ids.append(subscription.id)
                delete_fingerprints.append(endpoint_fingerprint(subscription.endpoint))
            else:
                keep_count += 1

        if delete_ids:
            session.query(PushSubscription).filter(
                PushSubscription.id.in_(delete_ids)
            ).delete(synchronize_session=False)
            session.commit()

    result = {
        "deleted": len(delete_ids),
        "kept": keep_count,
        "fingerprints": delete_fingerprints,
        "cutoff_hours": PRUNE_GRACE_HOURS,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

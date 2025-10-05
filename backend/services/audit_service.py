"""Audit service for structured event logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class AuditService:
    """Utility class for emitting structured audit events."""

    # ✅ Codex fix: Emit audit events with consistent JSON structure
    @staticmethod
    def log_event(
        user_id: str | None,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit event using structured JSON."""

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "service": "backend",
            "event": "audit",
            "user_id": user_id,
            "action": action,
            "metadata": metadata or {},
            "timestamp": timestamp,
        }
        logging.info(json.dumps(payload))


# ✅ Codex fix: Provide module-level shortcut for convenience
log_audit_event = AuditService.log_event

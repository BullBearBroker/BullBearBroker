from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import structlog

LOG_LEVEL = os.getenv("BULLBEAR_LOG_LEVEL", "INFO").upper()


@lru_cache(maxsize=1)
def _base_logger() -> structlog.stdlib.BoundLogger:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, LOG_LEVEL, logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("bullbearbroker")


def get_logger(**initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Return a configured structured logger, optionally binding context."""

    logger = _base_logger()
    if initial_context:
        return logger.bind(**initial_context)
    return logger


def log_event(
    logger: structlog.stdlib.BoundLogger,
    service: str,
    event: str,
    level: str = "warning",
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "service": service,
        "event": event,
        "level": level,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if extra:
        payload.update(extra)

    normalized_level = level.lower()
    log_method = getattr(logger, normalized_level, None)
    if not callable(log_method):
        log_method = logger.info

    log_method(payload)

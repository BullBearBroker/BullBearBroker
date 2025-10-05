"""Context helpers to propagate AI provider route information."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_provider_route: ContextVar[str] = ContextVar("ai_provider_route", default="sync")


def get_current_route() -> str:
    """Return the current provider route name (sync/stream/context)."""

    return _provider_route.get()


def set_route(route: str) -> Any:
    """Set the current provider route and return the reset token."""

    return _provider_route.set(route)


def reset_route(token: Any) -> None:
    """Reset the provider route using the provided context token."""

    _provider_route.reset(token)

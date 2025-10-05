from __future__ import annotations

import json
import logging
from typing import Any

import pytest
# ✅ Codex fix: HTTPX utilities for exercising middleware behavior
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_logging_middleware_logs_request(
    monkeypatch: pytest.MonkeyPatch,
    client: Any,
) -> None:
    """Ensure the structured logging middleware emits the expected log entry."""

    # ✅ Codex fix: Capture logging output for assertions
    logged_messages: list[str] = []

    def fake_info(message: str, *args: object, **kwargs: object) -> None:
        logged_messages.append(message)

    monkeypatch.setattr(logging, "info", fake_info)

    response = await client.get("/api/health")

    assert response.status_code == 200

    parsed_events = []
    for entry in logged_messages:
        try:
            data = json.loads(entry)
        except (TypeError, json.JSONDecodeError):
            continue
        if data.get("event") == "http_request":
            parsed_events.append(data)

    assert parsed_events, "Expected at least one structured log entry for the request"
    assert any(item.get("status") == 200 for item in parsed_events)


@pytest.mark.asyncio
async def test_unknown_route_returns_structured_error(client: Any) -> None:
    """Unknown routes should return a JSON error payload with a 404 status code."""

    # ✅ Codex fix: Trigger FastAPI's default 404 handling
    response = await client.get("/api/unknown")

    assert response.status_code == 404
    body = response.json()
    assert isinstance(body, dict)
    assert "detail" in body


@pytest.mark.asyncio
async def test_generic_exception_handled_globally() -> None:
    """Global exception handler should convert unexpected errors into 500 responses."""

    # ✅ Codex fix: Register a temporary route that raises an exception
    async def force_error() -> None:
        raise ValueError("forced error")

    route_count = len(app.router.routes)
    app.router.add_api_route("/api/force_error", force_error, methods=["GET"])

    # ✅ Codex fix: Use transport that preserves exception responses
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        try:
            response = await async_client.get("/api/force_error")
        finally:
            # ✅ Codex fix: Clean up temporary test route
            while len(app.router.routes) > route_count:
                app.router.routes.pop()

    assert response.status_code == 500
    assert response.json() == {"error": "Internal Server Error"}

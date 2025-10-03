from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient
from prometheus_client import CollectorRegistry, Counter
from starlette.requests import Request
from starlette.testclient import TestClient

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app  # noqa: E402
from backend.routers import alerts as alerts_router  # noqa: E402
from backend.tests.test_alerts_endpoints import (  # noqa: E402
    DummyUserService,
    _auth_header,
    _register_and_login,
)


@pytest.fixture(name="client")
def _client_fixture(async_client_fixture):  # noqa: ANN001
    return async_client_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected_status",
    [
        (
            {
                "title": "Sin activo",
                "condition": ">",
                "value": 10,
                "active": True,
            },
            400,
        ),
        (
            {
                "title": "Tipo incorrecto",
                "asset": "btc",
                "condition": ">",
                "value": "not-a-number",
            },
            422,
        ),
        (
            {
                "title": "Falta condición",
                "asset": "eth",
                "value": 1000,
            },
            422,
        ),
    ],
)
async def test_create_alert_invalid_payloads(
    client: AsyncClient,
    dummy_user_service: DummyUserService,
    payload: dict,
    expected_status: int,
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    response = await client.post(
        "/api/alerts",
        json=payload,
        headers=_auth_header(token),
    )

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_delete_nonexistent_alert_returns_404(
    client: AsyncClient,
    dummy_user_service: DummyUserService,
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    response = await client.delete(
        f"/api/alerts/{uuid.uuid4()}",
        headers=_auth_header(token),
    )

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_toggle_alert_activation(
    client: AsyncClient,
    dummy_user_service: DummyUserService,
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    create_payload = {
        "title": "BTC swing",
        "asset": "btc",
        "value": 42000,
        "condition": ">",
    }
    created = await client.post(
        "/api/alerts",
        json=create_payload,
        headers=_auth_header(token),
    )
    assert created.status_code == 201
    alert_id = created.json()["id"]

    disable = await client.put(
        f"/api/alerts/{alert_id}",
        json={"active": False},
        headers=_auth_header(token),
    )
    assert disable.status_code == 200
    assert disable.json()["active"] is False

    enable = await client.put(
        f"/api/alerts/{alert_id}",
        json={"active": True},
        headers=_auth_header(token),
    )
    assert enable.status_code == 200
    assert enable.json()["active"] is True


def test_websocket_subscription_and_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DummyUserService()
    monkeypatch.setattr(alerts_router, "user_service", service)
    monkeypatch.setattr(alerts_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None)

    with TestClient(app) as test_client:
        manager = app.state.alerts_ws_manager
        with test_client.websocket_connect("/ws/alerts") as connection:
            hello = connection.receive_json()
            assert hello["type"] == "system"
            assert test_client.portal.call(manager.count) == 1

        assert test_client.portal.call(manager.count) == 0


def test_alert_rate_limit_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = CollectorRegistry()
    counter = Counter(
        "alerts_rate_limited_total",
        "Alert operations blocked by rate limiting.",
        ["action"],
        registry=registry,
    )
    events: list[dict] = []

    def _capture_event(
        logger, **payload
    ):  # noqa: ANN001 - align with log_event signature
        events.append(payload)

    monkeypatch.setattr(alerts_router, "ALERTS_RATE_LIMITED", counter)
    monkeypatch.setattr(alerts_router, "log_event", _capture_event)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/alerts",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    request = Request(scope)

    alerts_router._record_alert_rate_limit(request, "create")

    assert counter.labels(action="create")._value.get() == pytest.approx(1.0)
    assert events and events[0]["event"] == "alerts_rate_limited"
    assert events[0]["action"] == "create"

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from backend.database import SessionLocal
from backend.main import app
from backend.models import PushSubscription
from backend.services.push_service import push_service


@pytest.mark.asyncio
async def test_push_subscription_and_send(monkeypatch):
    push_service._vapid_private_key = "test-private"  # type: ignore[attr-defined]
    push_service._vapid_public_key = "test-public"  # type: ignore[attr-defined]

    webpush_calls: list[dict] = []

    def fake_webpush(**kwargs):
        webpush_calls.append(kwargs)
        return None

    monkeypatch.setattr("backend.services.push_service.webpush", fake_webpush)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"push_{uuid.uuid4().hex}@test.com"
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "push1234"},
        )
        assert register.status_code in (200, 201)

        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "push1234"},
        )
        token = login.json()["access_token"]

        payload = {
            "endpoint": "https://example.com/push/1",
            "keys": {"auth": "auth-key", "p256dh": "p256dh-key"},
        }

        subscribe = await client.post(
            "/api/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert subscribe.status_code == 201, subscribe.text
        sub_id = subscribe.json()["id"]

        with SessionLocal() as db:
            record = db.query(PushSubscription).filter(PushSubscription.id == uuid.UUID(sub_id)).one()
            assert record.endpoint == payload["endpoint"]
            assert record.auth == payload["keys"]["auth"]
            assert record.p256dh == payload["keys"]["p256dh"]

        send = await client.post(
            "/api/push/send-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert send.status_code == 202, send.text
        assert send.json()["delivered"] == 1
        assert len(webpush_calls) == 1


@pytest.mark.asyncio
async def test_push_preferences_toggle_controls_delivery(monkeypatch):
    push_service._vapid_private_key = "test-private"  # type: ignore[attr-defined]
    push_service._vapid_public_key = "test-public"  # type: ignore[attr-defined]

    webpush_calls: list[dict] = []

    def fake_webpush(**kwargs):
        webpush_calls.append(kwargs)
        return None

    monkeypatch.setattr("backend.services.push_service.webpush", fake_webpush)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"push_pref_{uuid.uuid4().hex}@test.com"
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "push1234"},
        )
        assert register.status_code in (200, 201)

        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "push1234"},
        )
        token = login.json()["access_token"]

        payload = {
            "endpoint": "https://example.com/push/2",
            "keys": {"auth": "auth-key", "p256dh": "p256dh-key"},
        }

        subscribe = await client.post(
            "/api/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert subscribe.status_code == 201, subscribe.text

        disable = await client.put(
            "/api/push/preferences",
            headers={"Authorization": f"Bearer {token}"},
            json={"system": False},
        )
        assert disable.status_code == 200, disable.text
        assert disable.json()["system"] is False

        send_blocked = await client.post(
            "/api/push/send-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert send_blocked.status_code == 502
        assert not webpush_calls

        enable = await client.put(
            "/api/push/preferences",
            headers={"Authorization": f"Bearer {token}"},
            json={"system": True},
        )
        assert enable.status_code == 200
        assert enable.json()["system"] is True

        send_allowed = await client.post(
            "/api/push/send-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert send_allowed.status_code == 202
        assert send_allowed.json()["delivered"] == 1
        assert len(webpush_calls) == 1

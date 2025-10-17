# QA: Cobertura mínima del WebSocket de notificaciones sin alterar la lógica
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.main import app


def _register_and_login(client: TestClient) -> str:
    """Registra un usuario nuevo y devuelve un access token."""

    email = f"notifications_ws_{uuid.uuid4().hex}@test.com"
    payload = {
        "email": email,
        "password": "WsNotif123!",  # pragma: allowlist secret
    }  # pragma: allowlist secret  # pragma: allowlist secret
    client.post("/api/auth/register", json=payload)
    login = client.post("/api/auth/login", json=payload)
    return login.json()["access_token"]


def test_notifications_ws_requires_auth():
    # QA: sin token válido el socket se cierra con código de política (1008)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/notifications"):
                pass


def test_notifications_ws_ok():
    # QA: con token válido el handshake completa y permite intercambio básico
    with TestClient(app) as client:
        token = _register_and_login(client)
        with client.websocket_connect(f"/ws/notifications?token={token}") as ws:
            ws.send_text("ping")
            ws.close()

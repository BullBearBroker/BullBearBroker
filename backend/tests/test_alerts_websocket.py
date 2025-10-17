import pytest
from fastapi.testclient import TestClient

# QA: marcamos este módulo como e2e por abrir WebSocket real
pytestmark = pytest.mark.e2e

from backend.main import app


def test_alerts_websocket_ping_and_broadcast() -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/alerts") as connection,
    ):
        hello = connection.receive_json()
        assert hello["type"] == "system"

        connection.send_json({"type": "ping"})
        pong = connection.receive_json()
        assert pong == {"type": "pong"}

        connection.send_json({"type": "custom", "value": 42})
        ack = connection.receive_json()
        assert ack["type"] == "ack"
        assert ack["received"] == "custom"

        payload = {
            "type": "alert",
            "symbol": "BTCUSDT",
            "price": 42000.0,
        }

        client.portal.call(client.app.state.alerts_ws_manager.broadcast, payload)
        broadcast = connection.receive_json()
        assert broadcast == payload

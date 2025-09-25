import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_rate_limit_health():
    ok_count = 0
    too_many = 0
    for _ in range(6):
        response = client.get("/api/health")
        if response.status_code == 200:
            ok_count += 1
        elif response.status_code == 429:
            too_many += 1
    assert ok_count >= 5
    assert too_many >= 1


@pytest.mark.skip("End-to-end refresh flow pending integration with persistent users")
def test_refresh_flow():
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "secret"},
    )
    assert login.status_code in (200, 401)

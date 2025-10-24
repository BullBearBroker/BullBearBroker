import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not configured"
)


def test_health_includes_database_status():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code in {200, 503}

    services = response.json().get("services", {})
    database_info = services.get("database", {})
    status = database_info.get("status")
    assert status in {"ok", "error"}

    details = database_info.get("details", {})
    if os.getenv("DB_USE_POOL", "false").lower() == "true":
        assert details.get("pool") == "pgbouncer"

import uuid

import pytest
import pytest_asyncio
from fastapi_limiter import FastAPILimiter
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest_asyncio.fixture()
async def async_client() -> AsyncClient:
    transport = ASGITransport(app=app, client=(f"test-{uuid.uuid4()}", 80))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_app_lifespan_and_health(async_client: AsyncClient) -> None:
    """Ensure the app lifespan keeps Redis healthy and the health endpoint responds."""
    if FastAPILimiter.redis:
        pong = await FastAPILimiter.redis.ping()
        assert pong is True

    response = await async_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

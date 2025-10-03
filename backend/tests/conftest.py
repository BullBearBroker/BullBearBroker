import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path("/tmp/test_suite.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"  # ensure isolated DB for tests
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

import backend.models as _models  # noqa: F401  # ensure all ORM models are registered
from backend.database import engine
from backend.models import Base

from backend.main import app
from backend.routers import alerts as alerts_router, auth as auth_router
from backend.tests.test_alerts_endpoints import DummyUserService


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> None:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest_asyncio.fixture()
async def async_client() -> AsyncClient:
    """Create an AsyncClient bound to the FastAPI app for integration tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(name="client")
def client_fixture(async_client: AsyncClient) -> AsyncClient:
    """
    Wrapper para compatibilidad.
    Permite que los tests usen `client` aunque internamente siga siendo `async_client`.
    """
    return async_client


@pytest.fixture()
def dummy_user_service(monkeypatch: pytest.MonkeyPatch) -> DummyUserService:
    service = DummyUserService()

    monkeypatch.setattr(auth_router, "user_service", service)
    monkeypatch.setattr(alerts_router, "user_service", service)
    monkeypatch.setattr(
        auth_router, "UserAlreadyExistsError", service.UserAlreadyExistsError
    )
    monkeypatch.setattr(
        auth_router, "InvalidCredentialsError", service.InvalidCredentialsError
    )
    monkeypatch.setattr(
        alerts_router,
        "UserNotFoundError",
        service.UserNotFoundError,
        raising=False,
    )
    monkeypatch.setattr(auth_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None, raising=False)

    return service

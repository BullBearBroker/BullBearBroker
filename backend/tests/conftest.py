import os
import shutil
from pathlib import Path

# 🧩 Codex fix: configure isolated test database before loading backend modules
# QA: aislar DB SQLite por worker cuando pytest-xdist está activo
worker_id = os.getenv("PYTEST_XDIST_WORKER")
TEST_DB_PATH = (
    Path(f"/tmp/test_suite_{worker_id}.db") if worker_id else Path("/tmp/test_suite.db")
)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ.setdefault("TESTING", "1")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.core.rate_limit import reset_rate_limiter_cache
from backend.database import Base, engine
from backend.tests.test_alerts_endpoints import DummyUserService

from backend.main import app  # isort: skip
from backend.routers import alerts as alerts_router  # isort: skip
from backend.routers import auth as auth_router  # isort: skip


# QA: Prefijo por worker para evitar colisiones en Redis/RateLimiter al usar xdist
def pytest_configure(config):
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        os.environ.setdefault("BB_RATE_PREFIX", f"test:{worker}:")
        # QA: aislar caches/modelos por worker y evitar threads extra de tokenizers
        os.environ.setdefault("HF_HOME", f"/tmp/hf_cache_{worker}")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db() -> None:
    yield

    db_path = "bullbearbroker.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            tmp_copy = "bullbearbroker_test_copy.db"
            shutil.copy(db_path, tmp_copy)
            os.remove(tmp_copy)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="session", autouse=True)
def setup_db() -> None:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_rate_limits() -> None:
    reset_rate_limiter_cache()
    yield
    reset_rate_limiter_cache()


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
    monkeypatch.setattr(alerts_router, "UserNotFoundError", service.UserNotFoundError)
    monkeypatch.setattr(auth_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None)

    return service

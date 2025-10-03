import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from backend.main import app


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

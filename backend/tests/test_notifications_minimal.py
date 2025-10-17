# QA: Cobertura mínima de endpoints de notificaciones/push sin modificar lógica
import uuid

import pytest

# QA: forzamos backend asyncio para evitar dependencias de trio en xdist
pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    # QA: forzamos el backend asyncio para evitar dependencias opcionales
    return "asyncio"


@pytest.fixture
async def auth_async_client(async_client):
    """Devuelve un cliente autenticado reutilizando el helper global."""

    email = f"notifications_{uuid.uuid4().hex}@test.com"
    payload = {
        "email": email,
        "password": "NotifTest123!",  # pragma: allowlist secret
    }  # pragma: allowlist secret  # pragma: allowlist secret
    await async_client.post("/api/auth/register", json=payload)
    login = await async_client.post("/api/auth/login", json=payload)
    token = login.json()["access_token"]
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    try:
        yield async_client
    finally:
        async_client.headers.pop("Authorization", None)


@pytest.mark.anyio
async def test_notifications_requires_auth(async_client):
    # QA: la ruta de preferencias exige autenticación y responde 401/403 sin token
    response = await async_client.put("/api/push/preferences", json={})
    assert response.status_code in {401, 403}


@pytest.mark.anyio
async def test_notifications_read_invalid_payload(auth_async_client):
    # QA: payload no booleano provoca validación 422 en preferencias push
    response = await auth_async_client.put(
        "/api/push/preferences",
        json={"alerts": {"invalid": True}},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_notifications_list_ok(auth_async_client):
    # QA: flujo feliz - broadcast de prueba y consulta de logs devuelven 200
    broadcast = await auth_async_client.post("/api/notifications/test")
    assert broadcast.status_code in {200, 202}

    logs = await auth_async_client.get("/api/notifications/logs")
    assert logs.status_code == 200
    payload = logs.json()
    assert isinstance(payload, list)

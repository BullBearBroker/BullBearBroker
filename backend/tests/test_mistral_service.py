import pytest

from backend.services import mistral_service as mistral_module
from backend.services.mistral_service import MistralAPIError, MistralService


@pytest.fixture
def anyio_backend():
    return "asyncio"


class MockResponse:
    def __init__(self, status: int, json_data=None, text_data: str = ""):
        self.status = status
        self._json = json_data or {}
        self._text = text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return self._text


class MockSession:
    def __init__(self, responses: list[MockResponse]):
        self._responses = responses
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers, json, timeout):
        response = self._responses.pop(0)
        self.calls.append((json["model"], response.status))
        return response


class SessionFactory:
    def __init__(self, responses: list[MockResponse]):
        self.responses = responses
        self.last_session: MockSession | None = None

    def __call__(self, *args, **kwargs):
        session = MockSession(self.responses)
        self.last_session = session
        return session


@pytest.mark.anyio
async def test_fallback_to_small_on_429(monkeypatch):
    service = MistralService()
    service.api_key = "test-key"

    responses = [
        MockResponse(429, text_data="Too Many Requests"),
        MockResponse(429, text_data="Too Many Requests"),
        MockResponse(429, text_data="Too Many Requests"),
        MockResponse(
            200, json_data={"choices": [{"message": {"content": "fallback-small"}}]}
        ),
    ]
    factory = SessionFactory(responses)
    monkeypatch.setattr(mistral_module.aiohttp, "ClientSession", factory)

    async def immediate_sleep(delay):
        pass

    monkeypatch.setattr(mistral_module.asyncio, "sleep", immediate_sleep)

    result = await service.chat_completion(
        [{"role": "user", "content": "hola"}], model="medium"
    )

    assert result == "fallback-small"
    metrics = service.get_metrics()
    assert metrics["model_attempts"]["medium"] == 3
    assert metrics["model_attempts"]["small"] == 1
    assert factory.last_session is not None
    assert factory.last_session.calls[-1][0] == service.models["small"]


@pytest.mark.anyio
async def test_fallback_to_large_on_500(monkeypatch):
    service = MistralService()
    service.api_key = "test-key"

    responses = [
        MockResponse(500, text_data="Server Error"),
        MockResponse(500, text_data="Server Error"),
        MockResponse(500, text_data="Server Error"),
        MockResponse(500, text_data="Server Error"),
        MockResponse(500, text_data="Server Error"),
        MockResponse(500, text_data="Server Error"),
        MockResponse(
            200, json_data={"choices": [{"message": {"content": "fallback-large"}}]}
        ),
    ]
    factory = SessionFactory(responses)
    monkeypatch.setattr(mistral_module.aiohttp, "ClientSession", factory)

    async def immediate_sleep(delay):
        pass

    monkeypatch.setattr(mistral_module.asyncio, "sleep", immediate_sleep)

    result = await service.chat_completion(
        [{"role": "user", "content": "hola"}], model="medium"
    )

    assert result == "fallback-large"
    metrics = service.get_metrics()
    assert metrics["model_attempts"]["medium"] == 3
    assert metrics["model_attempts"]["small"] == 3
    assert metrics["model_attempts"]["large"] == 1
    assert factory.last_session is not None
    assert factory.last_session.calls[-1][0] == service.models["large"]


@pytest.mark.anyio
async def test_raises_error_body_for_4xx(monkeypatch):
    service = MistralService()
    service.api_key = "test-key"

    responses = [MockResponse(400, text_data="Bad Request")]
    factory = SessionFactory(responses)
    monkeypatch.setattr(mistral_module.aiohttp, "ClientSession", factory)

    async def immediate_sleep(delay):
        pass

    monkeypatch.setattr(mistral_module.asyncio, "sleep", immediate_sleep)

    with pytest.raises(MistralAPIError) as excinfo:
        await service.chat_completion(
            [{"role": "user", "content": "hola"}], model="small"
        )

    assert "Bad Request" in str(excinfo.value)
    metrics = service.get_metrics()
    assert metrics["model_attempts"]["small"] == 1

import asyncio
from unittest.mock import AsyncMock

import pytest

import backend.services.mistral_service as mistral_module
from backend.services.mistral_service import MistralAPIError, MistralService


class DummySession:
    async def __aenter__(self):  # noqa: D401 - simple context manager
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - simple context manager
        return None


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.fixture()
def service(monkeypatch: pytest.MonkeyPatch) -> MistralService:
    svc = MistralService()
    svc.api_key = "token"
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(mistral_module.aiohttp, "ClientSession", lambda: DummySession())
    return svc


@pytest.mark.anyio
async def test_chat_completion_fallbacks_to_small_on_429(service: MistralService, monkeypatch: pytest.MonkeyPatch) -> None:
    models_tried: list[str] = []

    async def fake_request(session, headers, payload):  # noqa: ANN001
        model = payload["model"]
        models_tried.append(model)
        if model == service.models["medium"]:
            raise MistralAPIError(429, "busy", model)
        return {"choices": [{"message": {"content": "small success"}}]}

    monkeypatch.setattr(service, "_perform_request", fake_request)

    response = await service.chat_completion([{"role": "user", "content": "hola"}], model="medium")

    assert response == "small success"
    assert service.models["medium"] in models_tried
    assert service.models["small"] in models_tried


@pytest.mark.anyio
async def test_chat_completion_uses_large_after_server_errors(service: MistralService, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(session, headers, payload):  # noqa: ANN001
        model = payload["model"]
        if model in (service.models["medium"], service.models["small"]):
            raise MistralAPIError(500, "server error", model)
        return {"choices": [{"message": {"content": "large success"}}]}

    monkeypatch.setattr(service, "_perform_request", fake_request)

    response = await service.chat_completion([{"role": "user", "content": "hola"}], model="medium")
    assert response == "large success"


@pytest.mark.anyio
async def test_analyze_market_sentiment_handles_corrupt_payload(service: MistralService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "chat_completion", AsyncMock(return_value="{not json}"))

    sentiment = await service.analyze_market_sentiment("Breaking news")
    assert sentiment == {"sentiment_score": 0.0, "confidence": 0.0, "keywords": []}


@pytest.mark.anyio
async def test_chat_completion_raises_clear_error_when_all_models_fail(service: MistralService, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(session, headers, payload):  # noqa: ANN001
        raise MistralAPIError(503, "unavailable", payload["model"])

    monkeypatch.setattr(service, "_perform_request", fake_request)

    with pytest.raises(MistralAPIError) as exc_info:
        await service.chat_completion([{"role": "user", "content": "hola"}], model="medium")

    assert exc_info.value.status == 503

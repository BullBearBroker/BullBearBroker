import asyncio
import os
import sys
from typing import Any

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.sentiment_service import SentimentService  # noqa: E402


class DummyCache:
    def __init__(self):
        self.values: dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(self, key: str, value: Any, ttl: Any = None):  # noqa: ARG002
        self.values[key.lower()] = value


class DummyResponse:
    def __init__(self, data: Any, status: int = 200):
        self._data = data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._data


class DummySession:
    def __init__(
        self, get_responses: list[DummyResponse], post_responses: list[DummyResponse]
    ):
        self.get_responses = get_responses
        self.post_responses = post_responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *_args, **_kwargs):
        return self.get_responses.pop(0)

    def post(self, *_args, **_kwargs):
        return self.post_responses.pop(0)


def make_service(get_data: list[DummyResponse], post_data: list[DummyResponse]):
    return SentimentService(
        market_cache=DummyCache(),
        text_cache=DummyCache(),
        session_factory=lambda timeout=None: DummySession(
            list(get_data), list(post_data)
        ),
    )


def test_sentiment_service_combines_sources():
    service = make_service(
        [
            DummyResponse(
                {
                    "data": [
                        {
                            "value": "50",
                            "value_classification": "Neutral",
                            "timestamp": "123",
                        }
                    ]
                }
            ),
        ],
        [
            DummyResponse([[{"label": "POSITIVE", "score": 0.9}]]),
        ],
    )

    result = asyncio.run(service.get_sentiment("AAPL", text="Apple is growing"))
    assert result["market_sentiment"]["classification"] == "Neutral"
    assert result["text_sentiment"]["label"] == "POSITIVE"


def test_sentiment_service_uses_cache_for_market():
    responses = [
        DummyResponse(
            {
                "data": [
                    {
                        "value": "20",
                        "value_classification": "Extreme Fear",
                        "timestamp": "1",
                    }
                ]
            }
        ),
    ]
    service = make_service(
        responses, [DummyResponse([[{"label": "NEGATIVE", "score": 0.7}]])]
    )

    first = asyncio.run(service.get_market_sentiment())
    second = asyncio.run(service.get_market_sentiment())
    assert first == second


def test_sentiment_service_returns_none_for_empty_text():
    service = make_service([], [])
    result = asyncio.run(service.analyze_text("   "))
    assert result is None

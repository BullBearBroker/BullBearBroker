import json
from typing import Any

import pytest
from httpx import AsyncClient
from prometheus_client import REGISTRY


async def _consume_stream(
    client: AsyncClient, payload: dict[str, Any]
) -> tuple[int, dict[str, str], list[str]]:
    async with client.stream("POST", "/api/ai/stream", json=payload) as response:
        status_code = response.status_code
        headers = dict(response.headers)
        chunks: list[str] = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                chunks.append(line[len("data: ") :])
        return status_code, headers, chunks


def _metric_value(name: str) -> float:
    value = REGISTRY.get_sample_value(name)
    return float(value) if value is not None else 0.0


@pytest.mark.asyncio
async def test_ai_stream_endpoint_returns_sse(async_client: AsyncClient) -> None:
    status, headers, chunks = await _consume_stream(
        async_client, {"message": "hola mundo"}
    )

    assert status == 200
    assert headers.get("content-type", "").startswith("text/event-stream")
    assert any(chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_ai_stream_endpoint_emits_chunks(async_client: AsyncClient) -> None:
    _, _, chunks = await _consume_stream(
        async_client, {"message": "probando el stream"}
    )

    # Debe emitir al menos los tokens y un chunk de finalización
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk  # No debe haber chunks vacíos


@pytest.mark.asyncio
async def test_ai_stream_metrics_are_updated(async_client: AsyncClient) -> None:
    tokens_before = _metric_value("ai_stream_tokens_total")
    duration_before = _metric_value("ai_stream_duration_seconds_sum")
    conversations_before = _metric_value("ai_conversations_active_total")

    _, _, chunks = await _consume_stream(
        async_client, {"message": "metricas en streaming"}
    )
    total_chunk_length = sum(len(chunk) for chunk in chunks)

    tokens_after = _metric_value("ai_stream_tokens_total")
    duration_after = _metric_value("ai_stream_duration_seconds_sum")
    conversations_after = _metric_value("ai_conversations_active_total")

    assert tokens_after >= tokens_before + total_chunk_length
    assert duration_after > duration_before
    assert conversations_after == conversations_before


@pytest.mark.asyncio
async def test_ai_stream_handles_exceptions(async_client: AsyncClient) -> None:
    status, _, chunks = await _consume_stream(async_client, {"message": ""})

    assert status == 200
    assert chunks, "El stream debe devolver al menos un chunk"
    error_payload = json.loads(chunks[-1])
    assert error_payload.get("error") is True
    assert "vacío" in error_payload.get("message", "")

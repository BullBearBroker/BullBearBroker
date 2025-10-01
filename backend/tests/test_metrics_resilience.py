import asyncio

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.requests import Request
from starlette.responses import Response

from backend.core import metrics
from backend.core.metrics import MetricsMiddleware


@pytest.fixture(autouse=True)
def reset_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = CollectorRegistry()
    request_count = Counter(
        "bullbearbroker_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "bullbearbroker_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        registry=registry,
    )
    monkeypatch.setattr(metrics, "REQUEST_COUNT", request_count)
    monkeypatch.setattr(metrics, "REQUEST_LATENCY", request_latency)


def _make_request(path: str = "/metrics") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover - used by pytest-asyncio
    return "asyncio"


def _histogram_sample_value(metric, *, name_suffix: str, labels: dict[str, str]) -> float:
    for metric_family in metric.collect():
        for sample in metric_family.samples:
            if sample.name.endswith(name_suffix) and sample.labels == labels:
                return sample.value
    raise AssertionError(f"Sample with suffix {name_suffix!r} and labels {labels!r} not found")


@pytest.mark.anyio
async def test_metrics_middleware_accumulates_counts_and_latency() -> None:
    middleware = MetricsMiddleware(lambda scope, receive, send: None)  # type: ignore[arg-type]
    request = _make_request("/resilience")

    async def call_next(_request):  # noqa: ANN001
        await asyncio.sleep(0)
        return Response(status_code=204)

    await middleware.dispatch(request, call_next)
    await middleware.dispatch(request, call_next)

    counter = metrics.REQUEST_COUNT.labels(method="GET", path="/resilience", status="204")
    assert counter._value.get() == pytest.approx(2.0)

    labels = {"method": "GET", "path": "/resilience"}
    count_value = _histogram_sample_value(metrics.REQUEST_LATENCY, name_suffix="_count", labels=labels)
    sum_value = _histogram_sample_value(metrics.REQUEST_LATENCY, name_suffix="_sum", labels=labels)
    assert count_value == pytest.approx(2.0)
    assert sum_value >= 0.0


@pytest.mark.anyio
async def test_metrics_middleware_records_failures() -> None:
    middleware = MetricsMiddleware(lambda scope, receive, send: None)  # type: ignore[arg-type]
    request = _make_request("/error")

    async def call_next(_request):  # noqa: ANN001
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await middleware.dispatch(request, call_next)

    counter = metrics.REQUEST_COUNT.labels(method="GET", path="/error", status="500")
    assert counter._value.get() == pytest.approx(1.0)

    labels = {"method": "GET", "path": "/error"}
    count_value = _histogram_sample_value(metrics.REQUEST_LATENCY, name_suffix="_count", labels=labels)
    assert count_value == pytest.approx(1.0)


def test_duplicate_metric_registration_and_invalid_inputs() -> None:
    counter = metrics.REQUEST_COUNT.labels(method="GET", path="/dup", status="200")
    counter.inc()
    counter.inc(3)
    assert counter._value.get() == pytest.approx(4.0)

    none_counter = metrics.REQUEST_COUNT.labels(method=None, path="/invalid", status="200")
    none_counter.inc()
    assert none_counter._value.get() == pytest.approx(1.0)

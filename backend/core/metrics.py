from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

try:  # pragma: no cover - dependencia opcional
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )
except ImportError:  # pragma: no cover - fallback sin cliente de Prometheus
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    class _NoopMetric:
        def __init__(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            pass

        def labels(self, **_kwargs):  # type: ignore[no-untyped-def]
            return self

        def observe(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return None

        def inc(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            return None

    class Counter(_NoopMetric):
        pass

    class Histogram(_NoopMetric):
        pass

    def generate_latest() -> bytes:  # type: ignore[override]
        return b"# prometheus_client not installed\n"


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "bullbearbroker_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "bullbearbroker_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

LOGIN_ATTEMPTS_TOTAL = Counter(
    "login_attempts_total",
    "Total login attempts grouped by outcome.",
    ["outcome"],
)
LOGIN_ATTEMPTS = LOGIN_ATTEMPTS_TOTAL
LOGIN_RATE_LIMITED = Counter(
    "login_rate_limited_total",
    "Login requests blocked by rate limiting.",
    ["dimension"],
)
LOGIN_DURATION = Histogram(
    "login_duration_seconds",
    "Duration of the login handler in seconds.",
)

ALERTS_RATE_LIMITED = Counter(
    "alerts_rate_limited_total",
    "Alert operations blocked by rate limiting.",
    ["action"],
)

AI_PROVIDER_FAILOVER_TOTAL = Counter(
    "ai_provider_failover_total",
    "Total AI provider failovers.",
    ["provider"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response: Response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
            REQUEST_COUNT.labels(method=method, path=path, status="500").inc()
            raise

        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
        REQUEST_COUNT.labels(
            method=method, path=path, status=str(response.status_code)
        ).inc()
        return response


metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> PlainTextResponse:
    payload = generate_latest()
    return PlainTextResponse(payload.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

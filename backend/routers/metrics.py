"""Prometheus metrics endpoints for backend observability."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# ✅ Codex fix: Define global Prometheus metrics used across the backend
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# ✅ Codex fix: Track request latency distribution per path
request_latency_seconds = Histogram(
    "request_latency_seconds",
    "Request latency",
    ["path"],
)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Expose Prometheus metrics in the standard text format."""

    # ✅ Codex fix: Return latest metrics snapshot with appropriate content type
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

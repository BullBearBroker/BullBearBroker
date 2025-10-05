"""Tests for audit logging and Prometheus metrics exposure."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from backend.services.audit_service import AuditService


# ✅ Codex fix: Utility to extract metric values safely
def _extract_metric(
    payload: str,
    *,
    method: str,
    path: str,
    status: str,
) -> float:
    for line in payload.splitlines():
        if not line.startswith("http_requests_total{"):
            continue

        try:
            label_segment, value_segment = line.split("} ", maxsplit=1)
        except ValueError:
            continue

        labels_raw = label_segment[len("http_requests_total{") :]
        label_pairs = [item for item in labels_raw.split(",") if item]
        parsed_labels: dict[str, str] = {}
        for pair in label_pairs:
            try:
                key, raw_value = pair.split("=", maxsplit=1)
            except ValueError:
                continue
            parsed_labels[key] = raw_value.strip('"')

        if (
            parsed_labels.get("method") == method
            and parsed_labels.get("path") == path
            and parsed_labels.get("status") == status
        ):
            try:
                value_text = value_segment.strip().split(" ", maxsplit=1)[0]
                return float(value_text)
            except ValueError:
                return 0.0
    return 0.0


def test_audit_service_logs_structured_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure audit events are emitted with the expected payload."""

    # ✅ Codex fix: Capture logging output for assertions
    captured_logs: list[str] = []

    def _fake_info(message: str, *args: Any, **kwargs: Any) -> None:
        captured_logs.append(message)

    monkeypatch.setattr(logging, "info", _fake_info)

    AuditService.log_event("user123", "login_success", {"ip": "127.0.0.1"})

    assert captured_logs, "Audit log was not emitted"
    payload = json.loads(captured_logs[0])
    assert payload["action"] == "login_success"
    assert payload["user_id"] == "user123"
    assert payload["metadata"] == {"ip": "127.0.0.1"}


@pytest.mark.asyncio()
async def test_metrics_endpoint_exposes_prometheus(async_client) -> None:
    """Verify that the /api/metrics endpoint returns Prometheus content."""

    # ✅ Codex fix: The metrics endpoint should be reachable and include counters
    response = await async_client.get("/api/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


@pytest.mark.asyncio()
async def test_http_request_metrics_accumulate(async_client) -> None:
    """Validate that repeated requests increment the custom counter."""

    # ✅ Codex fix: Record baseline metric snapshot
    before_response = await async_client.get("/api/metrics")
    baseline = _extract_metric(
        before_response.text,
        method="GET",
        path="/api/health",
        status="200",
    )

    for _ in range(2):
        health_response = await async_client.get("/api/health")
        assert health_response.status_code == 200

    after_response = await async_client.get("/api/metrics")
    updated_value = _extract_metric(
        after_response.text,
        method="GET",
        path="/api/health",
        status="200",
    )

    assert updated_value >= baseline + 2.0

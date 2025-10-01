from datetime import datetime, timedelta

import pytest

from backend.services.timeseries_service import resample_series


def test_resample_series_returns_empty_for_empty_input() -> None:
    assert resample_series([], "1h") == []


def test_resample_series_orders_points_correctly() -> None:
    series = [
        {"timestamp": "2024-01-01T02:00:00Z", "close": 20.0},
        {"timestamp": "2024-01-01T00:00:00Z", "close": 10.0},
        {"timestamp": "2024-01-01T01:00:00Z", "close": 15.0},
    ]

    buckets = resample_series(series, "1h")
    assert [bucket["timestamp"] for bucket in buckets] == [
        "2024-01-01T00:00:00Z",
        "2024-01-01T01:00:00Z",
        "2024-01-01T02:00:00Z",
    ]


def test_resample_series_preserves_gaps_without_creating_empty_buckets() -> None:
    series = [
        {"timestamp": "2024-01-01T00:10:00Z", "close": 10.0},
        {"timestamp": "2024-01-01T05:15:00Z", "close": 20.0},
        {"timestamp": "2024-01-02T08:45:00Z", "close": 30.0},
    ]

    buckets = resample_series(series, "1h")
    assert len(buckets) == 3
    assert buckets[0]["timestamp"] == "2024-01-01T00:00:00Z"
    assert buckets[1]["timestamp"] == "2024-01-01T05:00:00Z"
    assert buckets[2]["timestamp"] == "2024-01-02T08:00:00Z"


def test_resample_series_invalid_interval() -> None:
    with pytest.raises(ValueError):
        resample_series([{ "timestamp": "2024-01-01T00:00:00Z", "close": 1.0 }], "2m")


def test_resample_series_handles_large_dataset() -> None:
    start = datetime(2024, 1, 1)
    series = []
    for idx in range(1000):
        ts = (start + timedelta(hours=idx)).isoformat() + "Z"
        series.append({"timestamp": ts, "close": float(idx)})

    buckets = resample_series(series, "1h")
    assert len(buckets) == 1000
    assert buckets[0]["close"] == pytest.approx(0.0)
    assert buckets[-1]["close"] == pytest.approx(999.0)

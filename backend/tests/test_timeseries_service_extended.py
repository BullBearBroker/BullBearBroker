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


def test_resample_series_coalesces_duplicate_timestamps() -> None:
    series = [
        {"timestamp": "2024-01-01T00:00:00Z", "close": 100.0, "volume": 1.0},
        {"timestamp": "2024-01-01T00:00:00Z", "close": 102.0, "volume": 2.5},
        {"timestamp": "2024-01-01T00:30:00Z", "close": 101.0, "volume": 3.0},
    ]

    buckets = resample_series(series, "1h")
    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket["open"] == pytest.approx(100.0)
    assert bucket["high"] == pytest.approx(102.0)
    assert bucket["low"] == pytest.approx(100.0)
    assert bucket["close"] == pytest.approx(101.0)
    assert bucket["volume"] == pytest.approx(6.5)


def test_resample_series_with_irregular_gaps_preserves_actual_samples() -> None:
    series = [
        {"timestamp": "2024-01-01T00:45:00Z", "close": 10.0},
        {"timestamp": "2024-01-01T06:10:00Z", "close": 12.5},
        {"timestamp": "2024-01-02T12:30:00Z", "close": 20.0},
    ]

    buckets = resample_series(series, "4h")
    assert [bucket["timestamp"] for bucket in buckets] == [
        "2024-01-01T00:00:00Z",
        "2024-01-01T04:00:00Z",
        "2024-01-02T12:00:00Z",
    ]
    assert buckets[1]["open"] == pytest.approx(12.5)


def test_resample_series_accepts_interpolated_points_between_missing_samples() -> None:
    start = {"timestamp": "2024-01-01T00:00:00Z", "close": 100.0}
    end = {"timestamp": "2024-01-01T03:00:00Z", "close": 130.0}
    interpolated = ("2024-01-01T01:30:00Z", 115.0)

    buckets = resample_series([start, interpolated, end], "1h")
    assert [bucket["timestamp"] for bucket in buckets] == [
        "2024-01-01T00:00:00Z",
        "2024-01-01T01:00:00Z",
        "2024-01-01T03:00:00Z",
    ]
    assert buckets[1]["open"] == pytest.approx(115.0)
    assert buckets[1]["close"] == pytest.approx(115.0)

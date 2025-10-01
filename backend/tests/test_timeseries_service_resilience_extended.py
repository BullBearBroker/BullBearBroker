from datetime import datetime, timedelta, timezone

import pytest

from backend.services.timeseries_service import resample_series


def test_resample_series_returns_empty_for_empty_input() -> None:
    assert resample_series([], "1h") == []


def test_resample_series_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        resample_series([{ "timestamp": datetime.now(timezone.utc), "close": 1.0 }], "15m")


def test_resample_series_collapses_duplicate_buckets() -> None:
    base = datetime(2024, 1, 1, 12, 15, tzinfo=timezone.utc)
    series = [
        {"timestamp": base.isoformat(), "close": 10.0, "volume": 1.0},
        {"timestamp": (base + timedelta(minutes=10)).isoformat(), "close": 11.0, "volume": 2.0},
        {"timestamp": (base + timedelta(minutes=20)).isoformat(), "close": 12.0, "volume": 3.0},
    ]

    aggregated = resample_series(series, "1h")

    assert len(aggregated) == 1
    bucket = aggregated[0]
    assert bucket["open"] == 10.0
    assert bucket["close"] == 12.0
    assert bucket["high"] == 12.0
    assert bucket["low"] == 10.0
    assert bucket["volume"] == pytest.approx(6.0)


def test_resample_series_with_irregular_points() -> None:
    base = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    series = [
        (base + timedelta(minutes=5), 100.0, 1.0),
        (base + timedelta(hours=1, minutes=30), 110.0, 2.0),
        (base + timedelta(hours=1, minutes=45), 108.0, 0.5),
        (base + timedelta(hours=2, minutes=5), 112.0, None),
    ]

    aggregated = resample_series(series, "1h")

    assert len(aggregated) == 3
    assert aggregated[1]["high"] == 110.0
    assert aggregated[1]["low"] == 108.0


@pytest.mark.timeout(2)
def test_resample_series_handles_large_dataset_performance() -> None:
    base = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    series = []
    for index in range(20_000):
        timestamp = base + timedelta(minutes=index)
        series.append({"timestamp": timestamp.isoformat(), "close": float(index % 500), "volume": 1.0})

    buckets = resample_series(series, "1h")

    assert len(buckets) == pytest.approx(len(series) / 60, rel=0.1)
    assert buckets[0]["open"] == series[0]["close"]

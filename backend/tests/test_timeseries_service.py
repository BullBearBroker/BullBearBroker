from __future__ import annotations

from typing import List, Sequence

import pytest

from backend.services.timeseries_service import resample_series


@pytest.mark.parametrize(
    "interval, series, expected",
    [
        (
            "1h",
            [
                {"timestamp": "2024-01-01T00:15:00Z", "close": 10.0, "volume": 1},
                {"timestamp": "2024-01-01T00:45:00Z", "close": 12.0, "volume": 2},
                {"timestamp": "2024-01-01T01:10:00Z", "close": 9.0, "volume": 3},
                {"timestamp": "2024-01-01T02:05:00Z", "close": 11.0, "volume": 1},
            ],
            [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "open": 10.0,
                    "high": 12.0,
                    "low": 10.0,
                    "close": 12.0,
                    "volume": 3.0,
                },
                {
                    "timestamp": "2024-01-01T01:00:00Z",
                    "open": 9.0,
                    "high": 9.0,
                    "low": 9.0,
                    "close": 9.0,
                    "volume": 3.0,
                },
                {
                    "timestamp": "2024-01-01T02:00:00Z",
                    "open": 11.0,
                    "high": 11.0,
                    "low": 11.0,
                    "close": 11.0,
                    "volume": 1.0,
                },
            ],
        ),
        (
            "1d",
            [
                {"timestamp": "2024-01-01T10:00:00Z", "close": 100.0},
                {"timestamp": "2024-01-01T15:30:00Z", "close": 110.0},
                {"timestamp": "2024-01-02T09:30:00Z", "close": 90.0},
            ],
            [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "open": 100.0,
                    "high": 110.0,
                    "low": 100.0,
                    "close": 110.0,
                },
                {
                    "timestamp": "2024-01-02T00:00:00Z",
                    "open": 90.0,
                    "high": 90.0,
                    "low": 90.0,
                    "close": 90.0,
                },
            ],
        ),
    ],
)
def test_resample_series_returns_expected_buckets(
    interval: str, series: Sequence[dict], expected: List[dict]
) -> None:
    result = resample_series(series, interval)
    assert result == expected


def test_resample_series_handles_empty_input() -> None:
    assert resample_series([], "1h") == []


def test_resample_series_sorts_out_of_order_points() -> None:
    series = [
        ("2024-01-01T02:00:00Z", 20.0),
        ("2024-01-01T00:00:00Z", 10.0),
        ("2024-01-01T01:00:00Z", 15.0),
    ]
    result = resample_series(series, "1h")
    timestamps = [bucket["timestamp"] for bucket in result]
    assert timestamps == [
        "2024-01-01T00:00:00Z",
        "2024-01-01T01:00:00Z",
        "2024-01-01T02:00:00Z",
    ]


def test_resample_series_raises_for_invalid_interval() -> None:
    with pytest.raises(ValueError):
        resample_series([
            {"timestamp": "2024-01-01T00:00:00Z", "close": 1.0}
        ], "15m")

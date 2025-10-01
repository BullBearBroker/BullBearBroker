from datetime import datetime, timedelta

import pytest

from backend.services import timeseries_service as ts


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


def test_resample_series_rejects_unknown_interval():
    sample = [{"timestamp": "2023-01-01T00:00:00Z", "close": 1.0}]
    with pytest.raises(ValueError):
        ts.resample_series(sample, "1minute")


def test_resample_series_merges_duplicates_and_orders():
    base = datetime(2023, 1, 1, 0, 0, 0)
    series = [
        {"timestamp": (base + timedelta(minutes=5)).isoformat(), "close": 12.0, "volume": 3.0},
        {"timestamp": base.isoformat(), "close": 10.0, "volume": 1.0},
        {"timestamp": (base + timedelta(minutes=30)).isoformat(), "close": 11.5, "volume": 2.0},
        {"timestamp": (base + timedelta(hours=1)).isoformat(), "close": 9.0},
    ]

    aggregated = ts.resample_series(series, "1h")
    assert len(aggregated) == 2

    first, second = aggregated
    assert first["open"] == pytest.approx(10.0)
    assert first["close"] == pytest.approx(11.5)
    assert first["high"] == pytest.approx(12.0)
    assert first["low"] == pytest.approx(10.0)
    assert first["volume"] == pytest.approx(6.0)

    assert second["timestamp"].endswith("Z")
    assert second["close"] == pytest.approx(9.0)


def test_resample_series_rejects_corrupt_points():
    corrupt = [{"timestamp": None, "close": 10.0}]
    with pytest.raises((TypeError, ValueError)):
        ts.resample_series(corrupt, "1h")

    corrupt_price = [(datetime.utcnow().isoformat(), None)]
    with pytest.raises((TypeError, ValueError)):
        ts.resample_series(corrupt_price, "1h")


def test_resample_series_handles_large_dataset():
    base = datetime(2023, 1, 1)
    series = [
        {
            "timestamp": (base + timedelta(minutes=i)).isoformat(),
            "close": float(i % 50),
            "volume": float(i % 7),
        }
        for i in range(0, 5000)
    ]

    aggregated = ts.resample_series(series, "1h")
    expected = ((len(series) - 1) // 60) + 1
    assert len(aggregated) == expected


@pytest.mark.anyio
async def test_get_crypto_closes_rejects_invalid_interval():
    with pytest.raises(ValueError):
        await ts.get_crypto_closes_binance("BTCUSDT", "abc")

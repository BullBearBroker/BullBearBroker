from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services import timeseries_service as timeseries_module
from backend.services.timeseries_service import (
    _bucket_start,
    _normalize_point,
    _parse_timestamp,
    get_crypto_closes_binance,
    get_forex_closes,
    get_stock_closes,
    resample_series,
)


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
        resample_series([{"timestamp": "2024-01-01T00:00:00Z", "close": 1.0}], "2m")


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


def test_resample_series_merges_duplicates_with_mixed_input_types() -> None:
    series = [
        {"timestamp": "2024-01-01T00:15:00+00:00", "close": "100", "volume": "1"},
        (datetime(2024, 1, 1, 0, 15, tzinfo=UTC), 101.0, 2.0),
        {"time": "2024-01-01T00:45:00Z", "price": 102.0, "vol": 3.5},
    ]

    buckets = resample_series(series, "1h")
    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket["timestamp"] == "2024-01-01T00:00:00Z"
    assert bucket["open"] == pytest.approx(100.0)
    assert bucket["high"] == pytest.approx(102.0)
    assert bucket["low"] == pytest.approx(100.0)
    assert bucket["close"] == pytest.approx(102.0)
    assert bucket["volume"] == pytest.approx(6.5)


def test_resample_series_preserves_sparse_samples_without_padding() -> None:
    series = [
        {"timestamp": "2024-02-01T00:05:00Z", "close": 50.0},
        {"timestamp": "2024-02-01T07:20:00Z", "close": 75.0},
        {"timestamp": "2024-02-03T11:45:00Z", "close": 120.0},
    ]

    buckets = resample_series(series, "4h")
    assert [bucket["timestamp"] for bucket in buckets] == [
        "2024-02-01T00:00:00Z",
        "2024-02-01T04:00:00Z",
        "2024-02-03T08:00:00Z",
    ]
    assert buckets[1]["open"] == pytest.approx(75.0)


def test_resample_series_rejects_interval_aliases() -> None:
    sample = {"timestamp": "2024-01-01T00:00:00Z", "close": 10.0}
    with pytest.raises(ValueError):
        resample_series([sample], "5min")


def test_resample_series_handles_large_dataset_bucket_edges() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    series = []
    for idx in range(1500):
        ts = start + timedelta(hours=idx)
        series.append(
            {"timestamp": ts.isoformat().replace("+00:00", "Z"), "close": float(idx)}
        )

    buckets = resample_series(series, "1h")
    assert len(buckets) == 1500
    assert buckets[0]["timestamp"] == "2024-01-01T00:00:00Z"
    assert buckets[-1]["timestamp"] == "2024-03-03T11:00:00Z"
    assert buckets[-1]["close"] == pytest.approx(1499.0)


def test_resample_series_interpolated_point_with_daily_bucket() -> None:
    series = [
        {"timestamp": "2024-05-01T03:15:00Z", "close": 200.0},
        ("2024-05-01T12:00:00Z", 210.0),
        {"timestamp": "2024-05-02T01:00:00Z", "close": 190.0},
    ]

    buckets = resample_series(series, "1d")
    assert [bucket["timestamp"] for bucket in buckets] == [
        "2024-05-01T00:00:00Z",
        "2024-05-02T00:00:00Z",
    ]
    first = buckets[0]
    assert first["open"] == pytest.approx(200.0)
    assert first["high"] == pytest.approx(210.0)
    assert first["close"] == pytest.approx(210.0)


def test_parse_timestamp_supports_epoch_seconds() -> None:
    parsed = _parse_timestamp(1_700_000_000)
    assert parsed.tzinfo is not None
    assert parsed.isoformat().endswith("+00:00")


def test_parse_timestamp_rejects_empty_string() -> None:
    with pytest.raises(ValueError):
        _parse_timestamp("   ")


def test_parse_timestamp_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError):
        _parse_timestamp(object())


def test_normalize_point_requires_price_field() -> None:
    with pytest.raises(ValueError):
        _normalize_point({"timestamp": "2024-01-01T00:00:00Z"})


def test_normalize_point_sequence_requires_timestamp_and_price() -> None:
    with pytest.raises(ValueError):
        _normalize_point(["2024-01-01T00:00:00Z"])


def test_normalize_point_with_sequence_returns_expected_tuple() -> None:
    timestamp, price, volume = _normalize_point(("2024-01-01T00:00:00Z", "12.5", "7"))
    assert price == pytest.approx(12.5)
    assert volume == pytest.approx(7.0)
    assert timestamp.isoformat().endswith("+00:00")


def test_bucket_start_aligns_to_supported_intervals() -> None:
    daily = datetime(2024, 1, 2, 15, 45, tzinfo=UTC)
    assert _bucket_start(daily, "1d") == datetime(2024, 1, 2, tzinfo=UTC)

    four_hour = datetime(2024, 1, 2, 5, 30, tzinfo=UTC)
    assert _bucket_start(four_hour, "4h") == datetime(2024, 1, 2, 4, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_crypto_closes_binance_parses_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        [1700000000000, "1", "2", "0.5", "1.5", "10"],
        [1700003600000, "1.5", "3", "1", "2", "20"],
    ]
    http_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(timeseries_module, "_http_get_json", http_mock)

    closes, meta = await get_crypto_closes_binance("btcusdt", "1h", limit=2)

    assert closes == [1.5, 2.0]
    assert meta["highs"] == [2.0, 3.0]
    assert meta["lows"] == [0.5, 1.0]
    http_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_crypto_closes_binance_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        await get_crypto_closes_binance("btcusdt", "5m")


@pytest.mark.asyncio
async def test_get_stock_closes_prefers_twelvedata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")
    payload = {
        "values": [
            {"close": "10", "open": "9", "high": "11", "low": "8", "volume": "100"},
            {"close": "12", "open": "11", "high": "13", "low": "10", "volume": "120"},
        ]
    }
    http_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(timeseries_module, "_http_get_json", http_mock)

    closes, meta = await get_stock_closes("aapl", "1h", limit=2)

    assert closes == [10.0, 12.0]
    assert meta["source"] == "twelvedata"
    http_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_stock_closes_falls_back_to_alpha_vantage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")

    async def fake_http_get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
        if "twelvedata" in url:
            raise RuntimeError("twelvedata unavailable")
        if params.get("function") == "TIME_SERIES_INTRADAY":
            return {
                "Time Series (60min)": {
                    "2024-01-01 00:00:00": {
                        "1. open": "1",
                        "2. high": "2",
                        "3. low": "0.5",
                        "4. close": "1.5",
                        "5. volume": "10",
                    },
                    "2024-01-01 01:00:00": {
                        "1. open": "1.5",
                        "2. high": "2.5",
                        "3. low": "1.0",
                        "4. close": "2.0",
                        "5. volume": "12",
                    },
                }
            }
        raise AssertionError("Unexpected call")

    monkeypatch.setattr(timeseries_module, "_http_get_json", fake_http_get_json)

    closes, meta = await get_stock_closes("aapl", "1h", limit=2)

    assert closes == [1.5, 2.0]
    assert meta["source"] == "alpha_vantage"


@pytest.mark.asyncio
async def test_get_stock_closes_requires_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "")

    with pytest.raises(RuntimeError):
        await get_stock_closes("aapl", "1h")


@pytest.mark.asyncio
async def test_get_stock_closes_invalid_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")

    with pytest.raises(ValueError):
        await get_stock_closes("aapl", "5m")


@pytest.mark.asyncio
async def test_get_forex_closes_prefers_twelvedata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")

    payload = {
        "values": [
            {"close": "1.10", "high": "1.11", "low": "1.09", "open": "1.095"},
            {"close": "1.12"},
        ]
    }
    http_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(timeseries_module, "_http_get_json", http_mock)

    closes, meta = await get_forex_closes("eur/usd", "1h", limit=2)

    assert closes == [1.10, 1.12]
    assert meta["source"] == "twelvedata"
    assert meta["highs"] == [1.11, 1.12]
    assert meta["lows"] == [1.09, 1.12]
    assert meta["opens"] == [1.095, 1.12]
    assert meta["volumes"] == [0.0, 0.0]
    http_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_forex_closes_falls_back_to_alpha_vantage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")

    async def fake_http_get_json(url: str, params: dict[str, str]) -> dict[str, Any]:
        if "twelvedata" in url:
            raise RuntimeError("twelvedata down")
        assert params["function"] == "FX_INTRADAY"
        return {
            "Time Series FX (60min)": {
                "2024-01-01 00:00:00": {
                    "1. open": "1.1",
                    "2. high": "1.2",
                    "3. low": "1.0",
                    "4. close": "1.15",
                },
                "2024-01-01 01:00:00": {
                    "1. open": "1.15",
                    "2. high": "1.25",
                    "3. low": "1.05",
                    "4. close": "1.20",
                },
            }
        }

    monkeypatch.setattr(timeseries_module, "_http_get_json", fake_http_get_json)

    closes, meta = await get_forex_closes("eurusd", "1h", limit=2)

    assert closes == [1.15, 1.20]
    assert meta["source"] == "alpha_vantage"
    assert meta["note"].startswith("4h")
    assert meta["volumes"] == [0.0, 0.0]


@pytest.mark.asyncio
async def test_get_forex_closes_daily_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")

    daily_payload = {
        "Time Series FX (Daily)": {
            "2024-01-01": {
                "1. open": "1.1",
                "2. high": "1.2",
                "3. low": "1.0",
                "4. close": "1.15",
            },
            "2024-01-02": {
                "1. open": "1.15",
                "2. high": "1.25",
                "3. low": "1.05",
                "4. close": "1.20",
            },
        }
    }

    monkeypatch.setattr(
        timeseries_module, "_http_get_json", AsyncMock(return_value=daily_payload)
    )

    closes, meta = await get_forex_closes("eurusd", "1d", limit=2)

    assert closes == [1.15, 1.20]
    assert meta["source"] == "alpha_vantage"
    assert meta["interval"] == "1d"
    assert meta["opens"] == [1.1, 1.15]


@pytest.mark.asyncio
async def test_get_forex_closes_requires_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "")

    with pytest.raises(RuntimeError):
        await get_forex_closes("eurusd", "1h")


@pytest.mark.asyncio
async def test_get_forex_closes_rejects_unsupported_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_module, "TWELVEDATA_API_KEY", "token")
    monkeypatch.setattr(timeseries_module, "ALPHA_VANTAGE_API_KEY", "alpha")

    with pytest.raises(ValueError):
        await get_forex_closes("eurusd", "4h")

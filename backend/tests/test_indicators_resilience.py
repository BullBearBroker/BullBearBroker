import math

import pytest

from backend.utils import indicators


@pytest.mark.parametrize(
    "values, period, expected",
    [
        ([], 5, None),
        ([1.0], 3, None),
        ([1.0, 2.0], 5, None),
    ],
)
def test_ema_handles_insufficient_data(values: list[float], period: int, expected):
    assert indicators.ema(values, period) is expected


def test_macd_requires_enough_samples():
    assert indicators.macd([1.0] * 10) is None


def test_rsi_handles_small_series_and_constant_data():
    assert indicators.rsi([1.0] * 15, period=20) is None
    assert indicators.rsi([10.0] * 20, period=14) == 100.0


def test_bollinger_with_zero_mean_returns_none_bandwidth():
    data = [0.0] * 20
    bands = indicators.bollinger(data)
    assert bands is not None
    assert bands["bandwidth"] is None


def test_indicators_tolerate_extreme_values_without_crashing():
    series = [float("nan"), float("inf"), float("-inf")] + [
        float(i) for i in range(-5, 25)
    ]

    result = indicators.ema(series, period=3)
    assert result is None or math.isnan(result)

    atr = indicators.average_true_range(series, series, series, period=3)
    assert atr is None or isinstance(atr, float)

    finite_tail = [v for v in series if math.isfinite(v)][-20:]
    boll = indicators.bollinger(finite_tail)
    assert boll is not None
    assert set(boll.keys()) == {"middle", "upper", "lower", "bandwidth"}


def test_macd_long_series_runs_quickly():
    values = [float(i % 20) for i in range(5000)]
    result = indicators.macd(values)
    assert result is not None
    assert set(result.keys()) == {"macd", "signal", "hist"}


def test_stochastic_rsi_and_ichimoku_return_expected_types():
    closes = [float(i) for i in range(200)]
    stochastic = indicators.stochastic_rsi(closes, period=14, smooth_k=3, smooth_d=3)
    assert stochastic is not None
    assert set(stochastic.keys()) == {"%K", "%D"}

    highs = [p + 2.0 for p in closes]
    lows = [p - 2.0 for p in closes]
    ichimoku = indicators.ichimoku_cloud(highs, lows, closes)
    assert ichimoku is not None
    assert set(ichimoku.keys()) == {
        "tenkan_sen",
        "kijun_sen",
        "senkou_span_a",
        "senkou_span_b",
        "chikou_span",
    }


def test_volume_weighted_average_price_requires_nonzero_volume():
    result = indicators.volume_weighted_average_price([1.0], [1.0], [1.0], [0.0])
    assert result is None


def test_average_true_range_with_insufficient_data_returns_none():
    highs = [1.0, 2.0]
    lows = [0.5, 1.5]
    closes = [0.8, 1.8]
    assert indicators.average_true_range(highs, lows, closes, period=5) is None

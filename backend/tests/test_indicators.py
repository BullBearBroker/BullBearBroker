import math
from typing import List

import numpy as np
import pytest

from backend.utils import indicators


@pytest.mark.parametrize(
    "values, period, expected",
    [
        ([1, 2, 3, 4, 5], 3, 4.0),
        ([10, 11, 12, 13, 14, 15], 5, 13.0),
    ],
)
def test_ema_returns_float_for_simple_sequences(values: List[float], period: int, expected: float) -> None:
    result = indicators.ema(values, period)
    assert isinstance(result, float)
    assert result == pytest.approx(expected, rel=1e-6)

    series = indicators._ema_series(values, period)
    assert isinstance(series, list)
    assert len(series) == len(values)
    assert sum(value is None for value in series[: period - 1]) == period - 1


@pytest.mark.parametrize(
    "values, period, expected",
    [
        ([50, 51, 52, 53, 54, 55], 5, 100.0),
        ([55, 54, 53, 52, 51, 50], 5, 0.0),
    ],
)
def test_rsi_detects_trending_markets(values: List[float], period: int, expected: float) -> None:
    result = indicators.rsi(values, period)
    assert isinstance(result, float)
    assert result == pytest.approx(expected, abs=1e-2)

    series = indicators._rsi_series(values, period)
    assert isinstance(series, list)
    assert len(series) == len(values)
    assert any(value is not None for value in series)


def test_average_true_range_uses_high_low_close_sequences() -> None:
    highs = [10.0, 11.0, 12.5, 13.0, 13.5]
    lows = [8.5, 9.0, 10.2, 11.0, 11.5]
    closes = [9.5, 10.5, 11.8, 12.5, 13.2]

    result = indicators.average_true_range(highs, lows, closes, period=3)

    assert isinstance(result, float)
    assert result == pytest.approx(2.066667, rel=1e-6)


@pytest.mark.parametrize(
    "volumes, expected",
    [([1, 1, 1], 10.0), ([1, 2, 3], 10.333333)],
)
def test_volume_weighted_average_price_with_constant_and_variable_volume(volumes: List[float], expected: float) -> None:
    highs = np.array([10.0, 11.0, 12.0])
    lows = np.array([8.0, 9.0, 10.0])
    closes = np.array([9.0, 10.0, 11.0])

    result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)

    assert isinstance(result, float)
    assert result == pytest.approx(expected, rel=1e-6)


def test_volume_weighted_average_price_ignores_none_volume_entries() -> None:
    highs = [10.0, 10.5, 11.0]
    lows = [9.0, 9.5, 10.0]
    closes = [9.5, 10.0, 10.5]
    volumes = [1.0, None, 2.0]

    result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)

    assert isinstance(result, float)
    assert result == pytest.approx(10.166667, rel=1e-6)


def test_indicators_handle_short_series_and_zero_volume() -> None:
    assert indicators.ema([1.0, 2.0], 5) is None
    assert indicators.rsi([1.0, 1.0], period=5) is None
    assert indicators.macd([1.0] * 10) is None
    assert indicators.bollinger([1.0, 2.0, 3.0], period=5) is None
    assert indicators.average_true_range([1.0], [0.5], [0.8], period=3) is None
    assert indicators.stochastic_rsi([1.0] * 5, period=14) is None
    assert indicators.ichimoku_cloud([1.0] * 5, [0.5] * 5, [0.8] * 5, span_b_period=10) is None
    assert indicators.volume_weighted_average_price([1.0], [1.0], [1.0], [0.0]) is None


def test_indicators_manage_nan_and_negative_inputs() -> None:
    values = [0.0, -1.0, 2.0, float("nan"), -0.5, 3.0, 0.0, -2.0, 1.5, 0.0, 2.5, -1.0, 0.5, 0.0, 1.0]
    highs = [v + 0.5 if not math.isnan(v) else v for v in values]
    lows = [v - 0.5 if not math.isnan(v) else v for v in values]
    closes = values
    volumes = [1.0, 0.0, 2.0, float("nan"), 1.5, 2.0, 0.0, 3.0, 1.0, 0.0, 2.5, 1.0, 0.5, 0.0, 1.0]

    ema_result = indicators.ema(values, 3)
    assert ema_result is None or isinstance(ema_result, float)

    rsi_result = indicators.rsi(values, 5)
    assert rsi_result is None or isinstance(rsi_result, float)

    bollinger_result = indicators.bollinger(values, period=5)
    assert isinstance(bollinger_result, dict)
    assert all(
        (value is None) or isinstance(value, float)
        for value in bollinger_result.values()
    )

    atr_result = indicators.average_true_range(highs, lows, closes, period=5)
    assert atr_result is None or isinstance(atr_result, float)

    vwap_result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)
    assert vwap_result is None or isinstance(vwap_result, float)

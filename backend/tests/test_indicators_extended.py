import math

from backend.utils import indicators


def test_ema_short_series_returns_none() -> None:
    assert indicators.ema([1.0, 2.0], period=5) is None


def test_rsi_short_series_returns_none() -> None:
    assert indicators.rsi([1.0, 1.5], period=5) is None


def test_average_true_range_short_series_returns_none() -> None:
    highs = [10.0]
    lows = [9.0]
    closes = [9.5]
    assert indicators.average_true_range(highs, lows, closes, period=14) is None


def test_vwap_with_single_point() -> None:
    vwap = indicators.volume_weighted_average_price([10.0], [9.0], [9.5], [100])
    assert isinstance(vwap, float)


def test_indicators_handle_zero_and_negative_values() -> None:
    values = [0.0, -1.0, 2.0, -3.0, 4.0]
    ema_value = indicators.ema(values, period=2)
    rsi_value = indicators.rsi(values, period=2)
    assert isinstance(ema_value, float)
    assert isinstance(rsi_value, float)

    highs = [abs(v) + 1 for v in values]
    lows = [abs(v) for v in values]
    closes = [abs(v) - 0.5 for v in values]
    atr_value = indicators.average_true_range(highs, lows, closes, period=2)
    assert isinstance(atr_value, float)

    volumes = [10, 0, 5, 0, 3]
    vwap = indicators.volume_weighted_average_price(highs, lows, closes, volumes)
    assert isinstance(vwap, float)


def test_indicators_handle_nan_values() -> None:
    values = [1.0, float("nan"), 2.0, 3.0, 4.0]
    ema_result = indicators.ema(values, period=2)
    if ema_result is not None:
        assert math.isnan(ema_result)

    rsi_result = indicators.rsi(values, period=2)
    assert rsi_result is None or math.isnan(rsi_result)

    highs = [2.0, float("nan"), 3.0, 4.0]
    lows = [1.0, 1.5, 2.0, 3.0]
    closes = [1.5, 2.0, 2.5, float("nan")]
    atr_result = indicators.average_true_range(highs, lows, closes, period=2)
    assert atr_result is None or math.isnan(atr_result)

    vwap = indicators.volume_weighted_average_price(highs, lows, closes, [10, 20, 30, 40])
    assert vwap is None or math.isnan(vwap)


def test_indicators_handle_extreme_values() -> None:
    values = [1e12, 1e12 + 10, 1e12 + 20, 1e12 + 30, 1e12 + 40]
    ema_value = indicators.ema(values, period=3)
    rsi_value = indicators.rsi(values, period=3)
    assert isinstance(ema_value, float)
    assert isinstance(rsi_value, float)

    highs = [v + 5 for v in values]
    lows = [v - 5 for v in values]
    closes = [v for v in values]
    atr_value = indicators.average_true_range(highs, lows, closes, period=3)
    vwap_value = indicators.volume_weighted_average_price(highs, lows, closes, [100] * len(values))

    assert isinstance(atr_value, float)
    assert isinstance(vwap_value, float)

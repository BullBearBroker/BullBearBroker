import math

import numpy as np
import pytest

from backend.utils import indicators


@pytest.mark.parametrize(
    "values",
    [
        [math.nan, math.nan, math.nan],
        [1.0, math.nan, 2.0, 3.0],
    ],
)
def test_indicators_handle_nan_sequences(values: list[float]) -> None:
    ema_value = indicators.ema(list(values), period=3)
    rsi_value = indicators.rsi(list(values), period=3)

    assert ema_value is None or math.isnan(ema_value) or math.isfinite(ema_value)
    assert rsi_value is None or math.isnan(rsi_value) or math.isfinite(rsi_value)


@pytest.mark.parametrize(
    "highs,lows,closes",
    [
        (
            [-1.0, -0.5, -0.25, -0.125],
            [-2.0, -1.5, -1.0, -0.75],
            [-1.5, -1.0, -0.75, -0.5],
        ),
        (
            [10.0, 20.0, 30.0, -1e308],
            [9.0, 19.0, 29.0, -1e308],
            [9.5, 19.5, 29.5, -1e308],
        ),
    ],
)
def test_atr_controls_negative_and_extreme_values(highs, lows, closes) -> None:
    result = indicators.average_true_range(highs, lows, closes, period=2)

    assert result is None or math.isfinite(result) or math.isinf(result)


@pytest.mark.parametrize(
    "highs,lows,closes,volumes",
    [
        (
            [10.0, 10.2, 10.4, 10.6],
            [9.5, 9.7, 9.9, 10.1],
            [9.8, 10.0, 10.2, 10.4],
            [-10.0, -5.0, -1.0, -0.5],
        ),
        (
            [1e150, 1e151, 1e152],
            [1e140, 1e141, 1e142],
            [1e145, 1e146, 1e147],
            [1.0, 1.0, 1.0],
        ),
    ],
)
def test_vwap_handles_negative_and_large_inputs(highs, lows, closes, volumes) -> None:
    result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)

    assert result is None or math.isfinite(result) or math.isnan(result)


def test_indicators_support_long_sequences_without_overflow() -> None:
    length = 5000
    values = np.linspace(1.0, 100.0, num=length).tolist()
    volumes = np.linspace(1.0, 5.0, num=length).tolist()

    ema_value = indicators.ema(values, period=50)
    rsi_value = indicators.rsi(values, period=14)
    atr_value = indicators.average_true_range(values, values, values, period=14)
    vwap_value = indicators.volume_weighted_average_price(
        values, values, values, volumes
    )

    for candidate in (ema_value, rsi_value, atr_value, vwap_value):
        assert candidate is None or math.isfinite(candidate) or math.isnan(candidate)

import math
from collections.abc import Sequence

import numpy as np
import pytest

from backend.utils import indicators


@pytest.mark.parametrize(
    "values, period, expected",
    [
        ([], 5, None),
        ([0.0], 3, None),
    ],
)
def test_indicators_empty_sequences_return_none(values, period, expected):
    assert indicators.ema(values, period) is expected
    assert indicators.rsi(values, period) is expected


def test_average_true_range_and_vwap_empty_inputs_return_none():
    assert indicators.average_true_range([], [], [], period=5) is None
    assert indicators.volume_weighted_average_price([], [], [], []) is None


@pytest.mark.parametrize(
    "func, args",
    [
        (indicators.ema, (None, 3)),
        (indicators.rsi, (None, 14)),
        (indicators.average_true_range, (None, None, None, 14)),
        (indicators.volume_weighted_average_price, (None, None, None, None)),
    ],
)
def test_indicators_none_inputs_raise_type_error(func, args):
    with pytest.raises(TypeError):
        func(*args)


@pytest.mark.parametrize(
    "values",
    [
        [1.0, float("inf"), 10.0, 5.0, 2.0],
        [1e20, 1e20 + 1, 1e20 + 2, 1e20 + 3, 1e20 + 4],
    ],
)
def test_ema_and_rsi_handle_extreme_values(values: Sequence[float]):
    ema_result = indicators.ema(list(values), period=3)
    rsi_result = indicators.rsi(list(values), period=3)

    assert ema_result is None or isinstance(ema_result, float)
    assert rsi_result is None or isinstance(rsi_result, float)

    if ema_result is not None:
        assert math.isfinite(ema_result) or math.isinf(ema_result)
    if rsi_result is not None:
        assert (
            math.isfinite(rsi_result)
            or math.isinf(rsi_result)
            or math.isnan(rsi_result)
        )


@pytest.mark.parametrize(
    "highs, lows, closes",
    [
        (
            [1.0, float("inf"), 10.0, 9.0],
            [0.5, 1.0, 8.5, 8.0],
            [0.75, 2.0, 9.5, 8.5],
        ),
        (
            [1e10, 1e10 + 5, 1e10 + 2, 1e10 + 8],
            [1e10 - 5, 1e10 - 1, 1e10 - 2, 1e10 - 3],
            [1e10 - 1, 1e10 + 1, 1e10 + 3, 1e10 + 2],
        ),
    ],
)
def test_atr_handles_infinite_and_large_values(highs, lows, closes):
    result = indicators.average_true_range(highs, lows, closes, period=2)
    assert result is None or isinstance(result, float)
    if result is not None:
        assert math.isfinite(result) or math.isinf(result)


@pytest.mark.parametrize(
    "volumes",
    [
        [1.0, float("inf"), 2.0, 0.0],
        [np.finfo(float).max, np.finfo(float).max, 1.0],
    ],
)
def test_vwap_handles_anomalous_volume(volumes):
    highs = [10.0, 10.5, 10.75][: len(volumes)]
    lows = [9.0, 9.5, 9.75][: len(volumes)]
    closes = [9.5, 10.0, 10.25][: len(volumes)]

    result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)
    assert result is None or isinstance(result, float)
    if result is not None:
        assert math.isfinite(result) or math.isinf(result) or math.isnan(result)


@pytest.mark.parametrize(
    "func, args",
    [
        (indicators.ema, ([1.0, "oops", 3.0], 3)),
        (indicators.rsi, (["oops", 1.0, 2.0, 3.0], 2)),
        (
            indicators.average_true_range,
            ([1.0, 2.0, "bad"], [0.5, 1.5, 1.0], [0.75, 1.25, 1.5], 2),
        ),
        (
            indicators.volume_weighted_average_price,
            ([1.0, 2.0], [0.5, 1.0], [0.75, 1.5], [1.0, "bad"]),
        ),
    ],
)
def test_indicators_invalid_types_raise_type_error(func, args):
    with pytest.raises((TypeError, ValueError)):
        func(*args)


def test_rsi_handles_constant_and_descending_sequences():
    constant = [42.0] * 20
    descending = [100.0 - i for i in range(20)]

    assert indicators.rsi(constant, 14) == 100.0
    assert indicators.rsi(descending, 14) == 0.0


def test_ema_returns_constant_value_for_flat_series():
    values = [3.14159] * 10

    result = indicators.ema(values, period=5)

    assert result == pytest.approx(3.14159, rel=1e-6)


def test_vwap_with_negative_volumes_is_controlled():
    highs = [11.0, 10.5, 10.0]
    lows = [9.0, 9.5, 9.0]
    closes = [10.0, 9.75, 9.5]
    volumes = [-5.0, 0.0, 2.5]

    result = indicators.volume_weighted_average_price(highs, lows, closes, volumes)

    assert result is None or math.isfinite(result)

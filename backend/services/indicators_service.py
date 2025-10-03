"""Utility functions to compute common technical indicators."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "calculate_atr",
    "calculate_rsi",
    "calculate_ichimoku",
    "calculate_vwap",
]


def _ensure_positive_period(period: int) -> None:
    if period <= 0:
        raise ValueError("El periodo debe ser un entero positivo")


def _normalize_candles(prices: Sequence[Mapping[str, Any]]) -> list[dict[str, float]]:
    """Ensure the incoming candle payload contains the fields we need."""

    normalized: list[dict[str, float]] = []
    for index, candle in enumerate(prices):
        if not isinstance(candle, Mapping):
            raise ValueError("Cada vela debe ser un mapping con 'high', 'low' y 'close'")
        try:
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise ValueError("Cada vela debe incluir 'high', 'low' y 'close'") from exc
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive branch
            raise ValueError(
                f"Los valores de las velas deben ser numéricos (índice {index})"
            ) from exc

        normalized.append({"high": high, "low": low, "close": close})

    return normalized


def calculate_atr(prices: Sequence[Mapping[str, Any]], period: int = 14) -> float:
    """Calculate the Average True Range using high/low/close candles."""

    _ensure_positive_period(period)
    if not prices:
        raise ValueError("Se requieren datos de precios para calcular el ATR")

    candles = _normalize_candles(prices)

    true_ranges: list[float] = []
    previous_close: float | None = None

    for candle in candles:
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(tr)
        previous_close = close

    window = min(period, len(true_ranges))
    return sum(true_ranges[-window:]) / window


def calculate_rsi(prices: Sequence[float], period: int = 14) -> float:
    """Compute the Relative Strength Index for a series of closing prices."""

    _ensure_positive_period(period)
    price_series = [float(price) for price in prices]
    if len(price_series) < 2:
        raise ValueError("Se requieren al menos dos precios para calcular el RSI")

    changes = [price_series[i] - price_series[i - 1] for i in range(1, len(price_series))]
    effective_period = min(period, len(changes))

    gains = [max(change, 0.0) for change in changes[:effective_period]]
    losses = [max(-change, 0.0) for change in changes[:effective_period]]

    avg_gain = sum(gains) / effective_period
    avg_loss = sum(losses) / effective_period

    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0

    rs = avg_gain / avg_loss
    rsi_value = 100 - (100 / (1 + rs))

    for change in changes[effective_period:]:
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (effective_period - 1) + gain) / effective_period
        avg_loss = (avg_loss * (effective_period - 1) + loss) / effective_period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

    return rsi_value


def _midpoint(highs: Iterable[float], lows: Iterable[float]) -> float:
    highs_list = list(highs)
    lows_list = list(lows)
    if not highs_list or not lows_list:
        raise ValueError("Se requieren máximos y mínimos para calcular Ichimoku")
    return (max(highs_list) + min(lows_list)) / 2


def calculate_ichimoku(prices: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Return Tenkan-sen, Kijun-sen and Senkou spans for the given candles."""

    if not prices:
        raise ValueError("Se requieren velas para calcular Ichimoku")

    candles = _normalize_candles(prices)
    highs = [candle["high"] for candle in candles]
    lows = [candle["low"] for candle in candles]

    tenkan_period = min(9, len(highs))
    kijun_period = min(26, len(highs))
    span_b_period = min(52, len(highs))

    tenkan = _midpoint(highs[-tenkan_period:], lows[-tenkan_period:])
    kijun = _midpoint(highs[-kijun_period:], lows[-kijun_period:])
    span_a = (tenkan + kijun) / 2
    span_b = _midpoint(highs[-span_b_period:], lows[-span_b_period:])

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "span_a": span_a,
        "span_b": span_b,
    }


def calculate_vwap(prices: Sequence[float], volumes: Sequence[float]) -> float:
    """Compute the Volume Weighted Average Price for a price/volume series."""

    if not prices or not volumes:
        raise ValueError("Se requieren precios y volúmenes para calcular el VWAP")
    if len(prices) != len(volumes):
        raise ValueError("La longitud de precios y volúmenes debe coincidir")

    weighted_sum = 0.0
    volume_total = 0.0
    for price, volume in zip(prices, volumes, strict=False):
        price_float = float(price)
        volume_float = float(volume)
        weighted_sum += price_float * volume_float
        volume_total += volume_float

    if volume_total == 0:
        raise ValueError("El volumen total no puede ser cero al calcular el VWAP")

    return weighted_sum / volume_total

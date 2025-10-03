"""Utility functions to compute common technical indicators."""

from __future__ import annotations

from typing import Iterable


def _ensure_positive_period(period: int) -> None:
    if period <= 0:
        raise ValueError("El periodo debe ser un entero positivo")


def calculate_atr(prices: list[dict], period: int = 14) -> float:
    """Calculate the Average True Range using high/low/close candles."""

    _ensure_positive_period(period)
    if not prices:
        raise ValueError("Se requieren datos de precios para calcular el ATR")

    true_ranges: list[float] = []
    previous_close: float | None = None

    for candle in prices:
        try:
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("Cada vela debe incluir 'high', 'low' y 'close'") from exc

        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(tr)
        previous_close = close

    if not true_ranges:
        raise ValueError("No se pudieron calcular rangos verdaderos para el ATR")

    window = min(period, len(true_ranges))
    return sum(true_ranges[-window:]) / window


def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """Compute the Relative Strength Index for a series of closing prices."""

    _ensure_positive_period(period)
    if len(prices) < 2:
        raise ValueError("Se requieren al menos dos precios para calcular el RSI")

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
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


def calculate_ichimoku(prices: list[dict]) -> dict[str, float]:
    """Return Tenkan-sen, Kijun-sen and Senkou spans for the given candles."""

    if not prices:
        raise ValueError("Se requieren velas para calcular Ichimoku")

    highs = [float(candle["high"]) for candle in prices]
    lows = [float(candle["low"]) for candle in prices]

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


def calculate_vwap(prices: list[float], volumes: list[float]) -> float:
    """Compute the Volume Weighted Average Price for a price/volume series."""

    if not prices or not volumes:
        raise ValueError("Se requieren precios y volúmenes para calcular el VWAP")
    if len(prices) != len(volumes):
        raise ValueError("La longitud de precios y volúmenes debe coincidir")

    weighted_sum = 0.0
    volume_total = 0.0
    for price, volume in zip(prices, volumes, strict=False):
        volume_float = float(volume)
        weighted_sum += float(price) * volume_float
        volume_total += volume_float

    if volume_total == 0:
        raise ValueError("El volumen total no puede ser cero al calcular el VWAP")

    return weighted_sum / volume_total

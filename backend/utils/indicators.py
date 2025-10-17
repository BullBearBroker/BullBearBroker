# backend/utils/indicators.py

import math
from collections.abc import Sequence


def _ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    series: list[float | None] = [None] * (period - 1)
    ema_prev = sum(values[:period]) / period
    series.append(ema_prev)
    for price in values[period:]:
        ema_prev = price * k + ema_prev * (1 - k)
        series.append(ema_prev)
    return series


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return round(_ema_series(values, period)[-1] or 0.0, 6)


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi_val = 100 - (100 / (1 + rs))

    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else math.inf
        rsi_val = 100 - (100 / (1 + rs))

    return round(rsi_val, 2)


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, float] | None:
    if len(values) < slow + signal:
        return None
    ema_fast = _ema_series(values, fast)
    ema_slow = _ema_series(values, slow)
    macd_line: list[float | None] = []
    for f, s in zip(ema_fast, ema_slow, strict=False):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    macd_vals = [v for v in macd_line if v is not None]
    if len(macd_vals) < signal:
        return None

    k = 2 / (signal + 1)
    ema_prev = sum(macd_vals[:signal]) / signal
    for v in macd_vals[signal:]:
        ema_prev = v * k + ema_prev * (1 - k)

    macd_val = macd_vals[-1]
    signal_val = ema_prev
    hist = macd_val - signal_val
    return {
        "macd": round(macd_val, 6),
        "signal": round(signal_val, 6),
        "hist": round(hist, 6),
    }


def bollinger(
    values: list[float], period: int = 20, mult: float = 2.0
) -> dict[str, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period  # población
    sd = var**0.5
    upper = mid + mult * sd
    lower = mid - mult * sd
    bandwidth = (upper - lower) / mid if mid != 0 else None
    return {
        "middle": round(mid, 6),
        "upper": round(upper, 6),
        "lower": round(lower, 6),
        "bandwidth": round(bandwidth, 6) if bandwidth is not None else None,
    }


# [Codex] nuevo
def _rsi_series(values: Sequence[float], period: int) -> list[float | None]:
    """Devuelve la serie completa de RSI aplicando el cálculo incremental sobre ``values``."""
    if len(values) <= period:
        return [None] * len(values)

    rsis: list[float | None] = [None] * len(values)
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    rs_prev = avg_gain / avg_loss if avg_loss != 0 else math.inf
    rsis[period] = 100 - (100 / (1 + rs_prev))

    for idx in range(period + 1, len(values)):
        diff = values[idx] - values[idx - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else math.inf
        rsis[idx] = 100 - (100 / (1 + rs))

    return rsis


# [Codex] nuevo
def average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float | None:
    """Calcula el ATR (Average True Range) usando máximos, mínimos y cierres."""
    length = min(len(highs), len(lows), len(closes))
    if length <= period:
        return None

    trs: list[float] = []
    prev_close = closes[0]
    for idx in range(1, length):
        high = highs[idx]
        low = lows[idx]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = closes[idx]

    if len(trs) < period:
        return None

    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period

    return round(atr, 6)


# [Codex] nuevo
def stochastic_rsi(
    closes: Sequence[float],
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> dict[str, float] | None:
    """Calcula Stochastic RSI con suavizados %K y %D."""
    if len(closes) <= period + smooth_k + smooth_d:
        return None

    rsi_series = _rsi_series(closes, period)
    numeric_rsis = [value for value in rsi_series if value is not None]
    if len(numeric_rsis) < period:
        return None

    stoch_values: list[float] = []
    for idx in range(period, len(rsi_series)):
        current_rsi = rsi_series[idx]
        if current_rsi is None:
            continue
        start = max(period, idx - period + 1)
        window = [v for v in rsi_series[start : idx + 1] if v is not None]
        if not window:
            continue
        lowest = min(window)
        highest = max(window)
        if highest - lowest == 0:
            stoch_values.append(0.0)
        else:
            stoch_values.append((current_rsi - lowest) / (highest - lowest) * 100)

    if len(stoch_values) < smooth_k:
        return None

    def _sma(series: Sequence[float], size: int) -> float | None:
        if len(series) < size:
            return None
        return sum(series[-size:]) / size

    percent_k = _sma(stoch_values, smooth_k)
    if percent_k is None:
        return None

    percent_d_values = stoch_values[-(smooth_k + smooth_d - 1) :]
    percent_d = _sma(percent_d_values, smooth_d)
    if percent_d is None:
        return None

    return {
        "%K": round(percent_k, 2),
        "%D": round(percent_d, 2),
    }


# [Codex] nuevo
def ichimoku_cloud(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    conversion_period: int = 9,
    base_period: int = 26,
    span_b_period: int = 52,
) -> dict[str, float] | None:
    """Calcula líneas principales de Ichimoku Cloud."""
    length = min(len(highs), len(lows), len(closes))
    if length < span_b_period:
        return None

    def _mid(start_period: int) -> float:
        window_high = max(highs[-start_period:])
        window_low = min(lows[-start_period:])
        return (window_high + window_low) / 2

    tenkan = _mid(conversion_period)
    kijun = _mid(base_period)
    senkou_a = (tenkan + kijun) / 2
    span_b_high = max(highs[-span_b_period:])
    span_b_low = min(lows[-span_b_period:])
    senkou_b = (span_b_high + span_b_low) / 2
    chikou_index = length - base_period - 1
    chikou = closes[chikou_index] if chikou_index >= 0 else closes[0]

    return {
        "tenkan_sen": round(tenkan, 6),
        "kijun_sen": round(kijun, 6),
        "senkou_span_a": round(senkou_a, 6),
        "senkou_span_b": round(senkou_b, 6),
        "chikou_span": round(chikou, 6),
    }


# [Codex] nuevo
def volume_weighted_average_price(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> float | None:
    """Calcula la VWAP acumulada a partir de precios típicos y volumen."""
    length = min(len(highs), len(lows), len(closes), len(volumes))
    if length == 0:
        return None

    cumulative_pv = 0.0
    cumulative_volume = 0.0
    for idx in range(length):
        volume = volumes[idx]
        if volume is None:
            continue
        price_typ = (highs[idx] + lows[idx] + closes[idx]) / 3
        cumulative_pv += price_typ * volume
        cumulative_volume += volume

    if cumulative_volume == 0:
        return None

    return round(cumulative_pv / cumulative_volume, 6)

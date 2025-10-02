# backend/services/timeseries_service.py

from __future__ import annotations
import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import httpx

_HTTP_TIMEOUT_SECONDS = 15.0
_HTTP_CONNECT_TIMEOUT_SECONDS = 10.0
try:  # pragma: no cover - fallback for standalone usage
    from backend.utils.config import Config as _ConfigSource  # type: ignore

    _HTTP_TIMEOUT_SECONDS = float(
        getattr(_ConfigSource, "HTTPX_TIMEOUT_TIMESERIES", _HTTP_TIMEOUT_SECONDS)
    )
    _HTTP_CONNECT_TIMEOUT_SECONDS = float(
        getattr(
            _ConfigSource,
            "HTTPX_CONNECT_TIMEOUT_TIMESERIES",
            _HTTP_CONNECT_TIMEOUT_SECONDS,
        )
    )
except Exception:  # pragma: no cover - Config not available
    _ConfigSource = None  # type: ignore

# Leemos claves directamente del entorno (evitamos acoplar a utils.config)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

# Mapas de intervalos por proveedor
BINANCE_INTERVALS = {"1h": "1h", "4h": "4h", "1d": "1d"}
TWELVEDATA_INTERVALS = {"1h": "1h", "4h": "4h", "1d": "1day"}
ALPHAV_INTERVALS_STOCK = {"1h": "60min", "1d": "Daily"}  # 4h no está soportado
ALPHAV_INTERVALS_FX = {"1h": "60min", "1d": "Daily"}     # 4h no está soportado

DEFAULT_LIMIT = 300


_RESAMPLE_INTERVALS: Dict[str, int] = {"1h": 3600, "4h": 14_400, "1d": 86_400}


def _parse_timestamp(value: Any) -> datetime:
    """Convert different timestamp representations into a timezone-aware datetime."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Timestamp vacío no es válido")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:  # pragma: no cover - defensive, exercised via tests
            raise ValueError(f"Timestamp inválido: {value}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    raise TypeError(f"Tipo de timestamp no soportado: {type(value)!r}")


def _normalize_point(point: Mapping[str, Any] | Sequence[Any]) -> Tuple[datetime, float, Optional[float]]:
    """Extract timestamp, price and optional volume from incoming payloads."""

    if isinstance(point, Mapping):
        timestamp_raw = (
            point.get("timestamp")
            or point.get("time")
            or point.get("date")
        )
        if timestamp_raw is None:
            raise ValueError("Cada dato debe incluir 'timestamp'")
        price_raw = (
            point.get("close")
            if point.get("close") is not None
            else point.get("price")
        )
        if price_raw is None:
            raise ValueError("Cada dato debe incluir 'close' o 'price'")
        volume_raw = point.get("volume") or point.get("vol")
    else:
        if len(point) < 2:
            raise ValueError("Las muestras deben contener al menos timestamp y valor")
        timestamp_raw, price_raw = point[0], point[1]
        volume_raw = point[2] if len(point) > 2 else None

    timestamp = _parse_timestamp(timestamp_raw)
    price = float(price_raw)
    volume = None if volume_raw is None else float(volume_raw)
    return timestamp, price, volume


def _bucket_start(timestamp: datetime, interval: str) -> datetime:
    seconds = _RESAMPLE_INTERVALS.get(interval)
    if seconds is None:
        raise ValueError(f"Intervalo no soportado para resample: {interval}")

    if interval == "1d":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    if interval == "4h":
        hour_block = (timestamp.hour // 4) * 4
        return timestamp.replace(hour=hour_block, minute=0, second=0, microsecond=0)

    # Default to hourly buckets
    return timestamp.replace(minute=0, second=0, microsecond=0)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def resample_series(
    series: Sequence[Mapping[str, Any]] | Sequence[Sequence[Any]],
    interval: str,
) -> List[Dict[str, Any]]:
    """Aggregate raw candle data into OHLC buckets for the requested interval."""

    if not series:
        return []

    if interval not in _RESAMPLE_INTERVALS:
        raise ValueError("Intervalo no soportado para resample")

    normalized: List[Tuple[datetime, float, Optional[float]]] = []
    for point in series:
        normalized.append(_normalize_point(point))

    normalized.sort(key=lambda item: item[0])

    aggregated: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for timestamp, price, volume in normalized:
        bucket_ts = _bucket_start(timestamp, interval)
        bucket_key = _format_timestamp(bucket_ts)
        bucket = aggregated.get(bucket_key)
        if bucket is None:
            bucket = {
                "timestamp": bucket_key,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }
            if volume is not None:
                bucket["volume"] = volume
            aggregated[bucket_key] = bucket
        else:
            bucket["close"] = price
            bucket["high"] = max(bucket["high"], price)
            bucket["low"] = min(bucket["low"], price)
            if volume is not None:
                if "volume" in bucket:
                    bucket["volume"] += volume
                else:
                    bucket["volume"] = volume

    return list(aggregated.values())

async def _http_get_json(url: str, params: Dict[str, str]) -> Dict:
    timeout = httpx.Timeout(
        timeout=_HTTP_TIMEOUT_SECONDS,
        connect=_HTTP_CONNECT_TIMEOUT_SECONDS,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_crypto_closes_binance(symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> Tuple[List[float], Dict]:
    """
    symbol: p.ej. BTCUSDT
    """
    if interval not in BINANCE_INTERVALS:
        raise ValueError("Intervalo no soportado para Binance")
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": BINANCE_INTERVALS[interval], "limit": str(limit)}
    data = await _http_get_json(url, params)
    closes = [float(item[4]) for item in data]  # índice 4 = close
    highs = [float(item[2]) for item in data]  # [Codex] nuevo - capturamos máximos
    lows = [float(item[3]) for item in data]   # [Codex] nuevo - capturamos mínimos
    opens = [float(item[1]) for item in data]  # [Codex] nuevo - capturamos precios de apertura
    volumes = [float(item[5]) for item in data]  # [Codex] nuevo - volumen asociado
    meta = {
        "source": "binance",
        "interval": interval,
        "count": len(closes),
        "highs": highs,  # [Codex] nuevo
        "lows": lows,    # [Codex] nuevo
        "opens": opens,  # [Codex] nuevo
        "volumes": volumes,  # [Codex] nuevo
    }
    return closes, meta

async def get_stock_closes(symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> Tuple[List[float], Dict]:
    """
    Intenta TwelveData -> Alpha Vantage (fallback).
    """
    symbol = symbol.upper()

    # TwelveData
    if TWELVEDATA_API_KEY:
        if interval not in TWELVEDATA_INTERVALS:
            raise ValueError("Intervalo no soportado (TwelveData)")
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": TWELVEDATA_INTERVALS[interval],
            "outputsize": str(limit),
            "apikey": TWELVEDATA_API_KEY,
            "format": "JSON",
            "order": "ASC",  # de viejo -> nuevo para facilitar
        }
        try:
            data = await _http_get_json(url, params)
            if "values" in data:
                closes = [float(v["close"]) for v in data["values"]]
                highs = [float(v.get("high", v["close"])) for v in data["values"]]  # [Codex] nuevo
                lows = [float(v.get("low", v["close"])) for v in data["values"]]   # [Codex] nuevo
                opens = [float(v.get("open", v["close"])) for v in data["values"]]  # [Codex] nuevo
                volumes = [float(v.get("volume", 0.0) or 0.0) for v in data["values"]]  # [Codex] nuevo
                return closes, {
                    "source": "twelvedata",
                    "interval": interval,
                    "count": len(closes),
                    "highs": highs,  # [Codex] nuevo
                    "lows": lows,    # [Codex] nuevo
                    "opens": opens,  # [Codex] nuevo
                    "volumes": volumes,  # [Codex] nuevo
                }
        except Exception:
            pass  # seguimos al fallback

    # Alpha Vantage
    if not ALPHA_VANTAGE_API_KEY:
        raise RuntimeError("No hay claves para series históricas de acciones")

    if interval == "1h":
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "60min",
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        data = await _http_get_json(url, params)
        key = "Time Series (60min)"
        if key not in data:
            raise RuntimeError(f"Alpha Vantage error: {data.get('Note') or data.get('Error Message') or 'respuesta inválida'}")
        # ordenar por timestamp ascendente
        items = sorted(data[key].items(), key=lambda kv: kv[0])
        closes = [float(v["4. close"]) for _, v in items][-limit:]
        highs = [float(v.get("2. high", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        lows = [float(v.get("3. low", v["4. close"])) for _, v in items][-limit:]   # [Codex] nuevo
        opens = [float(v.get("1. open", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        volumes = [float(v.get("5. volume", 0.0) or 0.0) for _, v in items][-limit:]  # [Codex] nuevo
        return closes, {
            "source": "alpha_vantage",
            "interval": interval,
            "count": len(closes),
            "note": "4h no soportado por AV",
            "highs": highs,  # [Codex] nuevo
            "lows": lows,    # [Codex] nuevo
            "opens": opens,  # [Codex] nuevo
            "volumes": volumes,  # [Codex] nuevo
        }

    if interval == "1d":
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        data = await _http_get_json(url, params)
        key = "Time Series (Daily)"
        if key not in data:
            raise RuntimeError(f"Alpha Vantage error: {data.get('Note') or data.get('Error Message') or 'respuesta inválida'}")
        items = sorted(data[key].items(), key=lambda kv: kv[0])
        closes = [float(v["4. close"]) for _, v in items][-limit:]
        highs = [float(v.get("2. high", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        lows = [float(v.get("3. low", v["4. close"])) for _, v in items][-limit:]   # [Codex] nuevo
        opens = [float(v.get("1. open", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        volumes = [float(v.get("5. volume", 0.0) or 0.0) for _, v in items][-limit:]  # [Codex] nuevo
        return closes, {
            "source": "alpha_vantage",
            "interval": interval,
            "count": len(closes),
            "highs": highs,  # [Codex] nuevo
            "lows": lows,    # [Codex] nuevo
            "opens": opens,  # [Codex] nuevo
            "volumes": volumes,  # [Codex] nuevo
        }

    raise ValueError("Intervalo no soportado para acciones")

async def get_forex_closes(pair: str, interval: str, limit: int = DEFAULT_LIMIT) -> Tuple[List[float], Dict]:
    """
    pair: 'EURUSD' o 'EUR/USD'
    """
    pair = pair.upper().replace("/", "")
    base, quote = pair[:3], pair[3:]

    # TwelveData
    if TWELVEDATA_API_KEY:
        if interval not in TWELVEDATA_INTERVALS:
            raise ValueError("Intervalo no soportado (TwelveData)")
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": f"{base}/{quote}",
            "interval": TWELVEDATA_INTERVALS[interval],
            "outputsize": str(limit),
            "apikey": TWELVEDATA_API_KEY,
            "format": "JSON",
            "order": "ASC",
        }
        try:
            data = await _http_get_json(url, params)
            if "values" in data:
                closes = [float(v["close"]) for v in data["values"]]
                highs = [float(v.get("high", v["close"])) for v in data["values"]]  # [Codex] nuevo
                lows = [float(v.get("low", v["close"])) for v in data["values"]]    # [Codex] nuevo
                opens = [float(v.get("open", v["close"])) for v in data["values"]]  # [Codex] nuevo
                volumes = [float(v.get("volume", 0.0) or 0.0) for v in data["values"]]  # [Codex] nuevo
                return closes, {
                    "source": "twelvedata",
                    "interval": interval,
                    "count": len(closes),
                    "highs": highs,  # [Codex] nuevo
                    "lows": lows,    # [Codex] nuevo
                    "opens": opens,  # [Codex] nuevo
                    "volumes": volumes,  # [Codex] nuevo
                }
        except Exception:
            pass

    # Alpha Vantage
    if not ALPHA_VANTAGE_API_KEY:
        raise RuntimeError("No hay claves para series históricas de forex")

    url = "https://www.alphavantage.co/query"
    if interval == "1h":
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": base,
            "to_symbol": quote,
            "interval": "60min",
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        data = await _http_get_json(url, params)
        key = "Time Series FX (60min)"
        if key not in data:
            raise RuntimeError(f"Alpha Vantage error: {data.get('Note') or data.get('Error Message') or 'respuesta inválida'}")
        items = sorted(data[key].items(), key=lambda kv: kv[0])
        closes = [float(v["4. close"]) for _, v in items][-limit:]
        highs = [float(v.get("2. high", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        lows = [float(v.get("3. low", v["4. close"])) for _, v in items][-limit:]   # [Codex] nuevo
        opens = [float(v.get("1. open", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        return closes, {
            "source": "alpha_vantage",
            "interval": interval,
            "count": len(closes),
            "note": "4h no soportado por AV",
            "highs": highs,  # [Codex] nuevo
            "lows": lows,    # [Codex] nuevo
            "opens": opens,  # [Codex] nuevo
            "volumes": [0.0] * len(closes),  # [Codex] nuevo - FX AV no entrega volumen
        }

    if interval == "1d":
        params = {
            "function": "FX_DAILY",
            "from_symbol": base,
            "to_symbol": quote,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        data = await _http_get_json(url, params)
        key = "Time Series FX (Daily)"
        if key not in data:
            raise RuntimeError(f"Alpha Vantage error: {data.get('Note') or data.get('Error Message') or 'respuesta inválida'}")
        items = sorted(data[key].items(), key=lambda kv: kv[0])
        closes = [float(v["4. close"]) for _, v in items][-limit:]
        highs = [float(v.get("2. high", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        lows = [float(v.get("3. low", v["4. close"])) for _, v in items][-limit:]   # [Codex] nuevo
        opens = [float(v.get("1. open", v["4. close"])) for _, v in items][-limit:]  # [Codex] nuevo
        return closes, {
            "source": "alpha_vantage",
            "interval": interval,
            "count": len(closes),
            "highs": highs,  # [Codex] nuevo
            "lows": lows,    # [Codex] nuevo
            "opens": opens,  # [Codex] nuevo
            "volumes": [0.0] * len(closes),  # [Codex] nuevo - FX AV no entrega volumen
        }

    raise ValueError("Intervalo no soportado para forex")

async def get_closes(asset_type: str, symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> Tuple[List[float], Dict]:
    asset_type = asset_type.lower()
    interval = interval.lower()
    if asset_type == "crypto":
        return await get_crypto_closes_binance(symbol, interval, limit)
    if asset_type == "stock":
        return await get_stock_closes(symbol, interval, limit)
    if asset_type == "forex":
        return await get_forex_closes(symbol, interval, limit)
    raise ValueError("Tipo de activo no soportado")

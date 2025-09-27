# backend/services/timeseries_service.py

from __future__ import annotations
import os
from typing import Dict, List, Tuple, Optional
import httpx

# Leemos claves directamente del entorno (evitamos acoplar a utils.config)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

# Mapas de intervalos por proveedor
BINANCE_INTERVALS = {"1h": "1h", "4h": "4h", "1d": "1d"}
TWELVEDATA_INTERVALS = {"1h": "1h", "4h": "4h", "1d": "1day"}
ALPHAV_INTERVALS_STOCK = {"1h": "60min", "1d": "Daily"}  # 4h no está soportado
ALPHAV_INTERVALS_FX = {"1h": "60min", "1d": "Daily"}     # 4h no está soportado

DEFAULT_LIMIT = 300

async def _http_get_json(url: str, params: Dict[str, str]) -> Dict:
    timeout = httpx.Timeout(15.0, connect=10.0)
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

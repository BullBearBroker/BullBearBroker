"""Market-related API routes."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, HTTPException, Query

try:  # pragma: no cover - allow running from different entrypoints
    from services.market_service import market_service
    from services.forex_service import forex_service
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.services.market_service import market_service  # type: ignore
    from backend.services.forex_service import forex_service  # type: ignore

router = APIRouter(tags=["Markets"])


def _parse_symbols(raw: Sequence[str] | str) -> List[str]:
    if isinstance(raw, str):
        items = [item.strip() for item in raw.split(",")]
    else:
        items = [item.strip() for item in raw]
    normalized = [item for item in items if item]
    if not normalized:
        raise HTTPException(status_code=400, detail="Se requiere al menos un símbolo")
    return normalized


async def _collect_quotes(
    symbols: Sequence[str],
    fetcher,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    tasks = [asyncio.create_task(fetcher(symbol)) for symbol in symbols]
    results: List[Dict[str, Any]] = []
    missing: List[str] = []

    for symbol, task in zip(symbols, await asyncio.gather(*tasks, return_exceptions=True)):
        if isinstance(task, Exception):
            raise HTTPException(
                status_code=502,
                detail=f"Error obteniendo datos de {symbol}: {task}",
            ) from task
        if task:
            results.append(task)
        else:
            missing.append(symbol.upper())

    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron cotizaciones")

    return results, missing


@router.get("/crypto/prices")
async def get_crypto_prices(symbols: str = Query(..., description="Lista de símbolos separados por coma")) -> Dict[str, Any]:
    """Return crypto prices for the provided symbols."""

    parsed = _parse_symbols(symbols)
    quotes, missing = await _collect_quotes(parsed, market_service.get_crypto_price)
    return {"quotes": quotes, "missing": missing}


@router.get("/stocks/quotes")
async def get_stock_quotes(symbols: str = Query(..., description="Lista de tickers separados por coma")) -> Dict[str, Any]:
    """Return stock prices for the provided tickers."""

    parsed = _parse_symbols(symbols)
    quotes, missing = await _collect_quotes(parsed, market_service.get_stock_price)
    return {"quotes": quotes, "missing": missing}


@router.get("/forex/rates")
async def get_forex_rates(pairs: str = Query(..., description="Pares FX separados por coma")) -> Dict[str, Any]:
    """Return forex rates for the given currency pairs."""

    parsed = _parse_symbols(pairs)
    quotes, missing = await _collect_quotes(parsed, forex_service.get_quote)
    return {"quotes": quotes, "missing": missing}


@router.get("/crypto/{symbol}")
async def get_crypto(symbol: str) -> Dict[str, Any]:
    """Retrieve crypto pricing information ensuring service fallback order."""

    try:
        primary_price = await market_service.crypto_service.get_price(symbol)
    except Exception as exc:  # pragma: no cover - defensive logging happens in the service
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo precio de {symbol}: {exc}",
        ) from exc

    binance_data: Optional[Dict[str, Any]] = await market_service.get_binance_price(symbol)

    price: Optional[float] = primary_price if primary_price is not None else None
    if price is None and binance_data:
        try:
            price = float(binance_data.get("price")) if binance_data.get("price") is not None else None
        except (TypeError, ValueError):
            price = None

    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró información para {symbol}",
        )

    response: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "type": "crypto",
        "price": float(price),
        "source": "CryptoService" if primary_price is not None else None,
    }

    if binance_data:
        response.update(
            {
                "raw_change": binance_data.get("change"),
                "high": binance_data.get("high"),
                "low": binance_data.get("low"),
                "volume": binance_data.get("volume"),
            }
        )
        binance_source = binance_data.get("source")
        if response["source"] and binance_source:
            response["source"] = f"{response['source']} + {binance_source}"
        elif response["source"] is None:
            response["source"] = binance_source

    if response["source"] is None:
        response["source"] = "CryptoService"

    return response


@router.get("/stock/{symbol}")
async def get_stock(symbol: str) -> Dict[str, Any]:
    """Retrieve stock pricing information delegating to the StockService cascade."""

    try:
        result = await market_service.get_stock_price(symbol)
    except Exception as exc:  # pragma: no cover - defensive logging happens in the service
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo precio de {symbol}: {exc}",
        ) from exc

    if not result or result.get("price") is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró información para {symbol}",
        )

    return result


@router.get("/forex/{pair}")
async def get_forex(pair: str) -> Dict[str, Any]:
    """Retrieve forex quote information honouring the configured fallback chain."""

    try:
        result = await forex_service.get_quote(pair)
    except Exception as exc:  # pragma: no cover - defensive logging happens in the service
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo FX {pair}: {exc}",
        ) from exc

    if not result or result.get("price") is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró información para {pair}",
        )

    return result


# ============================================================
# NUEVO ENDPOINT: Indicadores técnicos (RSI, EMA, MACD, Bollinger)
# ============================================================

from backend.services.timeseries_service import get_closes
from backend.utils.indicators import (
    rsi,
    ema,
    macd,
    bollinger,
    average_true_range,  # [Codex] nuevo
    stochastic_rsi,      # [Codex] nuevo
    ichimoku_cloud,      # [Codex] nuevo
    volume_weighted_average_price,  # [Codex] nuevo
)

@router.get("/indicators")
async def get_indicators(
    type: str = Query(..., pattern="^(crypto|stock|forex)$"),
    symbol: str = Query(..., description="Ej: BTCUSDT, AAPL, EURUSD"),
    interval: str = Query("1h", pattern="^(1h|4h|1d)$"),
    limit: int = Query(300, ge=50, le=500),
    rsi_period: int = Query(14, ge=2, le=100),
    ema_periods: str = Query("20,50"),
    macd_fast: int = Query(12, ge=2, le=100),
    macd_slow: int = Query(26, ge=2, le=200),
    macd_signal: int = Query(9, ge=2, le=100),
    bb_period: int = Query(20, ge=5, le=200),
    bb_mult: float = Query(2.0, ge=0.1, le=5.0),
    include_atr: bool = Query(False),  # [Codex] nuevo
    atr_period: int = Query(14, ge=2, le=200),  # [Codex] nuevo
    include_stoch_rsi: bool = Query(False),  # [Codex] nuevo
    stoch_rsi_period: int = Query(14, ge=2, le=100),  # [Codex] nuevo
    stoch_rsi_k: int = Query(3, ge=1, le=10),  # [Codex] nuevo
    stoch_rsi_d: int = Query(3, ge=1, le=10),  # [Codex] nuevo
    include_ichimoku: bool = Query(False),  # [Codex] nuevo
    ichimoku_conversion: int = Query(9, ge=2, le=60),  # [Codex] nuevo
    ichimoku_base: int = Query(26, ge=2, le=120),  # [Codex] nuevo
    ichimoku_span_b: int = Query(52, ge=2, le=240),  # [Codex] nuevo
    include_vwap: bool = Query(False),  # [Codex] nuevo
):
    """
    Devuelve indicadores técnicos calculados sobre series históricas.
    """
    try:
        closes, meta = await get_closes(type, symbol, interval, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not closes or len(closes) < 30:
        raise HTTPException(status_code=400, detail="No hay suficientes datos para calcular indicadores")

    indicators: Dict[str, Any] = {"last_close": closes[-1]}

    highs = meta.get("highs") or []  # [Codex] nuevo
    lows = meta.get("lows") or []   # [Codex] nuevo
    volumes = meta.get("volumes") or []  # [Codex] nuevo

    rsi_val = rsi(closes, rsi_period)
    if rsi_val is not None:
        indicators["rsi"] = {"period": rsi_period, "value": rsi_val}

    # Múltiples EMAs
    try:
        periods = [int(x.strip()) for x in ema_periods.split(",") if x.strip()]
    except Exception:
        periods = [20, 50]
    ema_list = []
    for p in periods:
        val = ema(closes, p)
        if val is not None:
            ema_list.append({"period": p, "value": val})
    if ema_list:
        indicators["ema"] = ema_list

    macd_obj = macd(closes, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    if macd_obj:
        indicators["macd"] = {"fast": macd_fast, "slow": macd_slow, "signal": macd_signal, **macd_obj}

    bb_obj = bollinger(closes, period=bb_period, mult=bb_mult)
    if bb_obj:
        indicators["bollinger"] = {"period": bb_period, "mult": bb_mult, **bb_obj}

    if include_atr:
        atr_val = average_true_range(highs, lows, closes, period=atr_period)
        if atr_val is not None:
            indicators["atr"] = {"period": atr_period, "value": atr_val}  # [Codex] nuevo

    if include_stoch_rsi:
        stoch_val = stochastic_rsi(
            closes,
            period=stoch_rsi_period,
            smooth_k=stoch_rsi_k,
            smooth_d=stoch_rsi_d,
        )
        if stoch_val:
            indicators["stochastic_rsi"] = {
                "period": stoch_rsi_period,
                "smooth_k": stoch_rsi_k,
                "smooth_d": stoch_rsi_d,
                **stoch_val,
            }  # [Codex] nuevo

    if include_ichimoku:
        ichimoku_vals = ichimoku_cloud(
            highs,
            lows,
            closes,
            conversion_period=ichimoku_conversion,
            base_period=ichimoku_base,
            span_b_period=ichimoku_span_b,
        )
        if ichimoku_vals:
            indicators["ichimoku"] = {
                "conversion": ichimoku_conversion,
                "base": ichimoku_base,
                "span_b": ichimoku_span_b,
                **ichimoku_vals,
            }  # [Codex] nuevo

    if include_vwap:
        vwap_val = volume_weighted_average_price(highs, lows, closes, volumes)
        if vwap_val is not None:
            indicators["vwap"] = {"value": vwap_val}  # [Codex] nuevo

    return {
        "symbol": symbol.upper(),
        "type": type.lower(),
        "interval": interval.lower(),
        "count": len(closes),
        "source": meta.get("source"),
        "note": meta.get("note"),
        "indicators": indicators,
        "series": {
            "closes": closes,  # [Codex] nuevo
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
        },
    }

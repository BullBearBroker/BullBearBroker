"""Market-related API routes."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.core.logging_config import get_logger, log_event
from backend.services.timeseries_service import get_closes
from backend.utils.indicators import average_true_range  # [Codex] nuevo
from backend.utils.indicators import ichimoku_cloud  # [Codex] nuevo
from backend.utils.indicators import stochastic_rsi  # [Codex] nuevo
from backend.utils.indicators import volume_weighted_average_price  # [Codex] nuevo
from backend.utils.indicators import (
    bollinger,
    ema,
    macd,
    rsi,
)

try:  # pragma: no cover - allow running from different entrypoints
    from services.forex_service import forex_service
    from services.market_service import market_service
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.services.forex_service import forex_service  # type: ignore
    from backend.services.market_service import market_service  # type: ignore

logger = get_logger(service="markets_router")
router = APIRouter(tags=["Markets"])


def _parse_symbols(raw: Sequence[str] | str) -> list[str]:
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
) -> tuple[list[dict[str, Any]], list[str]]:
    tasks = [asyncio.create_task(fetcher(symbol)) for symbol in symbols]
    results: list[dict[str, Any]] = []
    missing: list[str] = []

    for symbol, task in zip(
        symbols, await asyncio.gather(*tasks, return_exceptions=True), strict=False
    ):
        if isinstance(task, Exception):
            log_event(
                logger,
                service="markets_router",
                event="quote_fetch_error",
                level="error",
                symbol=symbol,
                error=str(task),
            )
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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_candle(entry: Any) -> dict[str, Any] | None:
    if isinstance(entry, dict):
        timestamp = entry.get("timestamp") or entry.get("time")
        open_ = _to_float(entry.get("open") or entry.get("o"))
        high = _to_float(entry.get("high") or entry.get("h"))
        low = _to_float(entry.get("low") or entry.get("l"))
        close = _to_float(entry.get("close") or entry.get("c"))
        volume = _to_float(entry.get("volume") or entry.get("v"))
    elif isinstance(entry, list | tuple) and len(entry) >= 6:
        timestamp, open_, high, low, close, volume = entry[:6]
        open_ = _to_float(open_)
        high = _to_float(high)
        low = _to_float(low)
        close = _to_float(close)
        volume = _to_float(volume)
    else:
        return None

    if timestamp is None or None in (open_, high, low, close):
        return None

    return {
        "timestamp": str(timestamp),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _normalize_history_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    values = payload.get("values")
    if not isinstance(values, list):
        normalized_values: list[dict[str, Any]] = []
    else:
        normalized_values = []
        for entry in values:
            candle = _normalize_candle(entry)
            if candle is not None:
                normalized_values.append(candle)

    normalized: dict[str, Any] = dict(payload)
    normalized["values"] = normalized_values
    return normalized


@router.get("/crypto/prices")
async def get_crypto_prices(
    symbols: str = Query(..., description="Lista de símbolos separados por coma"),
) -> dict[str, Any]:
    """Return crypto prices for the provided symbols."""

    parsed = _parse_symbols(symbols)
    quotes, missing = await _collect_quotes(parsed, market_service.get_crypto_price)
    return {"quotes": quotes, "missing": missing}


@router.get("/stocks/quotes")
async def get_stock_quotes(
    symbols: str = Query(..., description="Lista de tickers separados por coma"),
) -> dict[str, Any]:
    """Return stock prices for the provided tickers."""

    parsed = _parse_symbols(symbols)
    quotes, missing = await _collect_quotes(parsed, market_service.get_stock_price)
    return {"quotes": quotes, "missing": missing}


@router.get("/forex/rates")
async def get_forex_rates(
    pairs: str = Query(..., description="Pares FX separados por coma"),
) -> dict[str, Any]:
    """Return forex rates for the given currency pairs."""

    parsed = _parse_symbols(pairs)
    quotes, missing = await _collect_quotes(parsed, forex_service.get_quote)
    return {"quotes": quotes, "missing": missing}


@router.get("/crypto/{symbol}")
async def get_crypto(symbol: str) -> dict[str, Any]:
    """Retrieve crypto pricing information ensuring service fallback order."""

    try:
        primary_price = await market_service.crypto_service.get_price(symbol)
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive logging happens in the service
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo precio de {symbol}: {exc}",
        ) from exc

    binance_data: dict[str, Any] | None = await market_service.get_binance_price(symbol)

    price: float | None = primary_price if primary_price is not None else None
    if price is None and binance_data:
        try:
            price = (
                float(binance_data.get("price"))
                if binance_data.get("price") is not None
                else None
            )
        except (TypeError, ValueError):
            price = None

    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró información para {symbol}",
        )

    response: dict[str, Any] = {
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


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    interval: str = Query("1h"),
    limit: int = Query(300, ge=10, le=1000),
    market: str = Query("auto", pattern="^(auto|crypto|stock|equity|forex)$"),
) -> dict[str, Any]:
    try:
        raw = await market_service.get_historical_ohlc(
            symbol, interval=interval, limit=limit, market=market
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - fallback controlado
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    history = _normalize_history_payload(raw)
    if not history or not history.get("values"):
        raise HTTPException(status_code=404, detail="No data found")

    return history


@router.get("/stock/{symbol}")
async def get_stock(symbol: str) -> dict[str, Any]:
    """Retrieve stock pricing information delegating to the StockService cascade."""

    try:
        result = await market_service.get_stock_price(symbol)
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive logging happens in the service
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
async def get_forex(pair: str) -> dict[str, Any]:
    """Retrieve forex quote information honouring the configured fallback chain."""

    try:
        result = await forex_service.get_quote(pair)
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive logging happens in the service
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
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    if not closes or len(closes) < 30:
        raise HTTPException(
            status_code=400,
            detail="No hay suficientes datos para calcular indicadores",
        )

    indicators: dict[str, Any] = {"last_close": closes[-1]}

    highs = meta.get("highs") or []  # [Codex] nuevo
    lows = meta.get("lows") or []  # [Codex] nuevo
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
        indicators["macd"] = {
            "fast": macd_fast,
            "slow": macd_slow,
            "signal": macd_signal,
            **macd_obj,
        }

    bb_obj = bollinger(closes, period=bb_period, mult=bb_mult)
    if bb_obj:
        indicators["bollinger"] = {
            "period": bb_period,
            "mult": bb_mult,
            **bb_obj,
        }

    if include_atr:
        atr_val = average_true_range(highs, lows, closes, period=atr_period)
        if atr_val is not None:
            indicators["atr"] = {
                "period": atr_period,
                "value": atr_val,
            }  # [Codex] nuevo

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

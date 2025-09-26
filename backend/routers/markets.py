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

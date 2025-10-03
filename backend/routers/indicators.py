"""REST endpoints to expose technical indicators for market symbols."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.services.indicators_service import (
    calculate_atr,
    calculate_ichimoku,
    calculate_rsi,
    calculate_vwap,
)
from backend.services.timeseries_service import get_closes

router = APIRouter(prefix="/api/indicators", tags=["Indicators"])


def _build_candles(data: list[float], metadata: dict[str, Any]) -> list[dict[str, float]]:
    highs = metadata.get("highs") or data
    lows = metadata.get("lows") or data

    length = len(data)
    candles: list[dict[str, float]] = []
    for index in range(length):
        high = float(highs[index]) if index < len(highs) else float(data[index])
        low = float(lows[index]) if index < len(lows) else float(data[index])
        close = float(data[index])
        candles.append({"high": high, "low": low, "close": close})
    return candles


def _normalize_volumes(length: int, metadata: dict[str, Any]) -> list[float]:
    volumes = metadata.get("volumes")
    if not volumes or len(volumes) != length:
        return [1.0] * length
    normalized: list[float] = []
    for volume in volumes:
        try:
            normalized.append(float(volume))
        except (TypeError, ValueError):
            normalized.append(0.0)
    if sum(normalized) == 0:
        return [1.0] * length
    return normalized


@router.get("/{symbol}")
async def get_indicators(
    symbol: str,
    asset_type: str = Query("crypto", description="Tipo de activo: crypto, stock o forex"),
    interval: str = Query("1d", description="Intervalo de tiempo (1h, 4h, 1d)"),
    limit: int = Query(100, ge=2, le=500, description="Número máximo de muestras"),
) -> dict[str, Any]:
    try:
        closes, metadata = await get_closes(asset_type, symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - resiliencia ante servicios externos
        raise HTTPException(status_code=502, detail=f"Error obteniendo datos: {exc}") from exc

    if not closes:
        raise HTTPException(status_code=404, detail="No se encontraron datos de precios")

    candles = _build_candles(closes, metadata)
    volumes = _normalize_volumes(len(closes), metadata)

    try:
        atr = calculate_atr(candles)
        rsi = calculate_rsi(closes)
        ichimoku = calculate_ichimoku(candles)
        vwap = calculate_vwap(closes, volumes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "indicators": {
            "atr": atr,
            "rsi": rsi,
            "ichimoku": ichimoku,
            "vwap": vwap,
        },
    }

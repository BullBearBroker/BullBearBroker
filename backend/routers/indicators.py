"""REST endpoints to expose technical indicators for market symbols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.services.indicators_service import (
    calculate_atr,
    calculate_ichimoku,
    calculate_rsi,
    calculate_vwap,
)
from backend.services.timeseries_service import get_closes

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


def _as_sequence(values: Any) -> Sequence[Any] | None:
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return values
    return None


def _build_candles(
    data: list[float], metadata: dict[str, Any]
) -> list[dict[str, float]]:
    highs = _as_sequence(metadata.get("highs"))
    lows = _as_sequence(metadata.get("lows"))
    opens = _as_sequence(metadata.get("opens"))

    candles: list[dict[str, float]] = []
    for index, close_value in enumerate(data):
        close = float(close_value)
        high = (
            float(highs[index]) if highs is not None and index < len(highs) else close
        )
        low = float(lows[index]) if lows is not None and index < len(lows) else close

        candle: dict[str, float] = {"high": high, "low": low, "close": close}

        if opens is not None and index < len(opens):
            try:
                candle["open"] = float(opens[index])
            except (TypeError, ValueError):  # pragma: no cover - datos inconsistentes
                pass

        candles.append(candle)

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
    asset_type: str = Query(
        "crypto", description="Tipo de activo: crypto, stock o forex"
    ),
    interval: str = Query("1d", description="Intervalo de tiempo (1h, 4h, 1d)"),
    limit: int = Query(100, ge=2, le=500, description="Número máximo de muestras"),
) -> dict[str, Any]:
    try:
        closes, metadata = await get_closes(asset_type, symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - resiliencia ante servicios externos
        raise HTTPException(
            status_code=502, detail=f"Error obteniendo datos: {exc}"
        ) from exc

    if not closes:
        raise HTTPException(
            status_code=404, detail="No se encontraron datos de precios"
        )

    try:
        closes = [float(value) for value in closes]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail=f"Datos de cierre inválidos: {exc}"
        ) from exc

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

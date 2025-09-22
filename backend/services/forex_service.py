from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from utils.config import Config


class ForexService:
    """Cliente centralizado para datos de divisas."""

    _TWELVEDATA_BASE_URL = "https://api.twelvedata.com"
    _YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def __init__(self) -> None:
        self._api_key = Config.TWELVEDATA_API_KEY
        self._timeout = aiohttp.ClientTimeout(total=20)

    @staticmethod
    def _normalize_pair(pair: str) -> str:
        sanitized = pair.replace("-", "").replace("/", "").replace("_", "")
        sanitized = sanitized.upper()
        if len(sanitized) < 6:
            raise ValueError("El par de divisas debe tener al menos 6 caracteres, por ejemplo EURUSD")
        base = sanitized[:3]
        quote = sanitized[3:]
        return f"{base}/{quote}"

    @staticmethod
    def _yahoo_symbol(normalized_pair: str) -> str:
        base, quote = normalized_pair.split("/")
        return f"{base}{quote}=X"

    async def _fetch_twelvedata_rate(self, normalized_pair: str) -> Optional[Dict[str, Any]]:
        if not self._api_key:
            return None
        params = {"symbol": normalized_pair, "apikey": self._api_key}
        url = f"{self._TWELVEDATA_BASE_URL}/exchange_rate?{urlencode(params)}"
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"TwelveData devolvió estado {response.status}")
                payload = await response.json()
                if "rate" not in payload:
                    raise RuntimeError(f"Respuesta inesperada de TwelveData: {payload}")
                return {
                    "source": "twelvedata",
                    "price": float(payload["rate"]),
                    "timestamp": payload.get("timestamp"),
                }

    async def _fetch_yahoo_rate(self, normalized_pair: str) -> Optional[Dict[str, Any]]:
        symbol = self._yahoo_symbol(normalized_pair)
        params = {"range": "1d", "interval": "1m"}
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(f"{self._YAHOO_CHART_URL}{symbol}", params=params) as response:
                if response.status != 200:
                    raise RuntimeError(f"Yahoo Finance devolvió estado {response.status}")
                payload = await response.json()
                result = (payload.get("chart", {}).get("result") or [None])[0]
                if not result:
                    raise RuntimeError(f"Respuesta inesperada de Yahoo Finance: {payload}")
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                if price is None:
                    raise RuntimeError("Yahoo Finance no devolvió regularMarketPrice")
                return {
                    "source": "yahoo",
                    "price": float(price),
                    "timestamp": meta.get("regularMarketTime"),
                }

    async def get_exchange_rate(self, pair: str) -> Dict[str, Any]:
        normalized_pair = self._normalize_pair(pair)
        tasks = [
            self._fetch_twelvedata_rate(normalized_pair),
            self._fetch_yahoo_rate(normalized_pair),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated: Dict[str, Any] = {"pair": normalized_pair, "sources": {}, "errors": []}
        rates: List[float] = []

        for result in results:
            if isinstance(result, Exception):
                aggregated["errors"].append(str(result))
                continue
            if result is None:
                continue
            source = result.pop("source")
            aggregated["sources"][source] = result
            price = result.get("price")
            if isinstance(price, (int, float)):
                rates.append(float(price))

        aggregated["errors"] = [error for error in aggregated["errors"] if error]
        aggregated["composite_rate"] = sum(rates) / len(rates) if rates else None
        return aggregated

    async def get_time_series(
        self, pair: str, interval: str = "1h", outputsize: int = 120
    ) -> List[Dict[str, Any]]:
        normalized_pair = self._normalize_pair(pair)
        if not self._api_key:
            raise RuntimeError("TWELVEDATA_API_KEY es requerido para series temporales")

        params = {
            "symbol": normalized_pair,
            "interval": interval,
            "outputsize": str(outputsize),
            "apikey": self._api_key,
            "format": "JSON",
        }
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(f"{self._TWELVEDATA_BASE_URL}/time_series", params=params) as response:
                if response.status != 200:
                    raise RuntimeError(f"TwelveData devolvió estado {response.status}")
                payload = await response.json()
                values = payload.get("values")
                if not values:
                    raise RuntimeError(f"Respuesta inesperada de TwelveData: {payload}")
                series: List[Dict[str, Any]] = []
                for item in reversed(values):  # ordenar cronológicamente
                    timestamp = datetime.fromisoformat(item["datetime"])
                    series.append(
                        {
                            "datetime": timestamp,
                            "open": float(item["open"]),
                            "high": float(item["high"]),
                            "low": float(item["low"]),
                            "close": float(item["close"]),
                        }
                    )
                return series


forex_service = ForexService()

"""Servicio para obtener cotizaciones de divisas y materias primas."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout, ContentTypeError

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from backend.utils.cache import CacheClient
    from backend.utils.config import Config
except ImportError:  # pragma: no cover
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]


class ForexService:
    """Permite consultar precios de pares FX y materias primas."""

    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = 0.75

    def __init__(
        self,
        *,
        cache_client: CacheClient | None = None,
        session_factory=aiohttp.ClientSession,
    ) -> None:
        self.cache = cache_client or CacheClient("forex-quotes", ttl=60)
        self._session_factory = session_factory
        self._timeout = ClientTimeout(total=10)
        # Orden de fallback: Twelve Data → Alpha Vantage → Yahoo Finance
        self.apis = (
            {
                "name": "Twelve Data",
                "callable": self._fetch_twelvedata,
                "requires_key": True,
                "api_key": Config.TWELVEDATA_API_KEY,
            },
            {
                "name": "Alpha Vantage",
                "callable": self._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": Config.ALPHA_VANTAGE_API_KEY,
            },
            {
                "name": "Yahoo Finance",
                "callable": self._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        )

    async def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """Devuelve información de precio para ``symbol``."""

        normalized = self._normalize_symbol(symbol)
        cache_key = normalized.replace("/", "-")
        cached_value = await self.cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        async with self._session_factory(timeout=self._timeout) as session:
            attempted_sources: list[str] = []
            for api in self.apis:
                if api["requires_key"] and not api["api_key"]:
                    continue

                attempted_sources.append(api["name"])
                result = await self._call_with_retries(
                    api["callable"], session, normalized, api["name"]
                )
                if result:
                    payload = {
                        "symbol": normalized,
                        "price": result["price"],
                        "change": result.get("change"),
                        "source": api["name"],
                        "sources": attempted_sources.copy(),
                    }
                    await self.cache.set(cache_key, payload)
                    return payload

        return None

    async def get_quotes(self, symbols: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Obtiene cotizaciones para múltiples símbolos."""

        results: dict[str, dict[str, Any] | None] = {}
        for symbol in symbols:
            results[symbol] = await self.get_quote(symbol)
        return results

    async def _call_with_retries(
        self,
        handler,
        session: aiohttp.ClientSession,
        symbol: str,
        source_name: str,
    ) -> dict[str, Any] | None:
        backoff = self.RETRY_BACKOFF
        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            try:
                return await handler(session, symbol)
            except (
                TimeoutError,
                KeyError,
                ValueError,
                ClientError,
                ContentTypeError,
                TypeError,
            ) as exc:
                print(
                    "ForexService: intento "
                    f"{attempt} fallido con {source_name} para {symbol}: {exc}"
                )
            except Exception as exc:  # pragma: no cover - errores inesperados
                print(
                    f"ForexService: error inesperado con {source_name} para {symbol}: {exc}"
                )
                break
            await asyncio.sleep(backoff)
            backoff *= 2
        return None

    async def _fetch_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        source_name: str,
    ) -> dict[str, Any]:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status >= 400:
                raise ClientError(f"{source_name} devolvió estado {response.status}")
            return await response.json()

    async def _fetch_twelvedata(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> dict[str, Any]:
        if not Config.TWELVEDATA_API_KEY:
            raise KeyError("TWELVEDATA_API_KEY no configurada")
        url = "https://api.twelvedata.com/quote"
        params = {"symbol": symbol, "apikey": Config.TWELVEDATA_API_KEY}
        data = await self._fetch_json(
            session, url, params=params, source_name="Twelve Data"
        )
        price = float(data["close"])
        percent_change = data.get("percent_change") or data.get("change_percent")
        change = float(percent_change) if percent_change is not None else None
        return {"price": price, "change": change}

    async def _fetch_yahoo_finance(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> dict[str, Any]:
        yahoo_symbol = self._to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        data = await self._fetch_json(
            session, url, source_name="Yahoo Finance"
        )
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        change = meta.get("regularMarketChangePercent")
        change_value = float(change) if change is not None else None
        return {"price": price, "change": change_value}

    async def _fetch_alpha_vantage(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> dict[str, Any]:
        if not Config.ALPHA_VANTAGE_API_KEY:
            raise KeyError("ALPHA_VANTAGE_API_KEY no configurada")

        base, quote = self._split_symbol(symbol)
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": base,
            "to_currency": quote,
            "apikey": Config.ALPHA_VANTAGE_API_KEY,
        }
        data = await self._fetch_json(
            session, url, params=params, source_name="Alpha Vantage"
        )

        info = data.get("Realtime Currency Exchange Rate")
        if not isinstance(info, dict):
            raise KeyError("Respuesta inválida de Alpha Vantage")

        price = float(info["5. Exchange Rate"])
        change = info.get("9. Ask Price") or info.get("8. Bid Price")
        change_value = float(change) if change is not None else None
        return {"price": price, "change": change_value}

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        symbol = symbol.strip().upper().replace("-", "/")
        if symbol.count("/") == 0 and len(symbol) == 6:
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    @staticmethod
    def _to_yahoo_symbol(symbol: str) -> str:
        if "/" in symbol:
            base, quote = symbol.split("/")
            return f"{base}{quote}=X"
        # Símbolos de materias primas suelen coincidir con Yahoo
        return symbol

    @staticmethod
    def _split_symbol(symbol: str) -> tuple[str, str]:
        normalized = ForexService._normalize_symbol(symbol)
        if "/" in normalized:
            base, quote = normalized.split("/", maxsplit=1)
            return base, quote
        if len(normalized) == 6:
            return normalized[:3], normalized[3:]
        raise ValueError(f"Símbolo FX inválido: {symbol}")


forex_service = ForexService()

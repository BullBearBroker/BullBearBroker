import asyncio
from json import JSONDecodeError
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout, ContentTypeError

try:  # pragma: no cover
    from backend.utils.cache import CacheClient
    from backend.utils.config import Config
except ImportError:  # pragma: no cover
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]


class StockService:
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = 0.75

    def __init__(
        self,
        cache_client: CacheClient | None = None,
        session_factory=aiohttp.ClientSession,
    ) -> None:
        self.cache = cache_client or CacheClient("stock-prices", ttl=45)
        self._session_factory = session_factory
        self._timeout = ClientTimeout(total=10)
        self.apis = [
            {
                "name": "Alpha Vantage",
                "callable": self._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": Config.ALPHA_VANTAGE_API_KEY,
            },
            {
                "name": "Twelve Data",
                "callable": self._fetch_twelvedata,
                "requires_key": True,
                "api_key": Config.TWELVEDATA_API_KEY,
            },
            {
                "name": "Yahoo Finance",
                "callable": self._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ]

    async def get_price(self, symbol: str) -> dict[str, Any] | None:
        """Obtiene precio, variación y fuente de un símbolo bursátil."""

        cache_key = symbol.upper()
        cached_value = await self.cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        async with self._session_factory(timeout=self._timeout) as session:
            for api in self.apis:
                if api["requires_key"] and not api["api_key"]:
                    continue

                result = await self._call_with_retries(
                    api["callable"], session, symbol, api["name"]
                )
                if result:
                    payload = {
                        "price": result["price"],
                        "change": result["change"],
                        "source": api["name"],
                    }
                    await self.cache.set(cache_key, payload)
                    print(f"StockService: usando {api['name']} para {symbol}")
                    return payload

        return None

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
                JSONDecodeError,
                KeyError,
                ClientError,
                ContentTypeError,
                TypeError,
                ValueError,
            ) as exc:
                print(
                    "StockService: intento "
                    f"{attempt} fallido con {source_name} para {symbol}: {exc}"
                )
            except Exception as exc:  # pragma: no cover - errores inesperados
                print(
                    f"StockService: error inesperado con {source_name} para {symbol}: {exc}"
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
            try:
                return await response.json()
            except ContentTypeError as exc:
                text = await response.text()
                raise JSONDecodeError("Respuesta no JSON", text, 0) from exc

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
        percent_change = data.get("percent_change") or data.get("change_percent", 0)
        change = float(percent_change) if percent_change is not None else 0.0
        return {"price": price, "change": change}

    async def _fetch_yahoo_finance(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> dict[str, Any]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        data = await self._fetch_json(session, url, source_name="Yahoo Finance")
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        change = float(meta.get("regularMarketChangePercent", 0.0) or 0.0)
        return {"price": price, "change": change}

    async def _fetch_alpha_vantage(
        self, session: aiohttp.ClientSession, symbol: str
    ) -> dict[str, Any]:
        if not Config.ALPHA_VANTAGE_API_KEY:
            raise KeyError("ALPHA_VANTAGE_API_KEY no configurada")
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": Config.ALPHA_VANTAGE_API_KEY,
        }
        data = await self._fetch_json(
            session, url, params=params, source_name="Alpha Vantage"
        )
        quote = data["Global Quote"]
        price = float(quote["05. price"])
        change_percent = quote.get("10. change percent")
        if isinstance(change_percent, str):
            change_percent = change_percent.replace("%", "").strip()
        change = float(change_percent) if change_percent else 0.0
        return {"price": price, "change": change}


stock_service = StockService()

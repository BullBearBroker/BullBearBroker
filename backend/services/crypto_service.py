import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientError, ClientTimeout

from utils.config import Config

try:
    import redis.asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is optional
    redis_asyncio = None


@dataclass(frozen=True)
class PriceResult:
    source: str
    price: float


class CryptoService:
    def __init__(
        self,
        redis_client: Optional["redis_asyncio.Redis"] = None,
        cache_ttl: Optional[int] = None,
    ) -> None:
        self._timeout = ClientTimeout(total=Config.CRYPTO_HTTP_TIMEOUT)
        self._max_retries = Config.CRYPTO_HTTP_RETRIES
        self._backoff_base = Config.CRYPTO_HTTP_BACKOFF_BASE
        self._redis = redis_client or self._build_redis_client()
        self._cache_ttl = cache_ttl or Config.CRYPTO_PRICE_CACHE_TTL

        self.apis = {
            "primary": ("coingecko", self.coingecko),
            "secondary": ("binance", self.binance),
            "fallback": ("coinmarketcap", self.coinmarketcap),
        }

    def _build_redis_client(self) -> Optional["redis_asyncio.Redis"]:
        if not Config.REDIS_URL or redis_asyncio is None:
            return None
        return redis_asyncio.from_url(
            Config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def get_price(self, symbol: str) -> Optional[Dict[str, object]]:
        """Obtener precio crypto de múltiples fuentes con caché y tolerancia a fallos."""

        normalized_symbol = symbol.upper().strip()
        if not normalized_symbol:
            raise ValueError("El símbolo de la criptomoneda es requerido")

        cached = await self._get_cached_price(normalized_symbol)
        if cached is not None:
            return cached

        fetchers = [
            self._fetch_price_from_source(name, func, normalized_symbol)
            for name, func in self.apis.values()
        ]

        results = await asyncio.gather(*fetchers, return_exceptions=True)
        valid_prices = self._process_results(results)

        if not valid_prices:
            return None

        price, source = self._calculate_final_price(valid_prices)
        payload = {
            "symbol": normalized_symbol,
            "price": price,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._set_cached_price(normalized_symbol, payload)
        return payload

    async def _get_cached_price(self, symbol: str) -> Optional[Dict[str, object]]:
        if not self._redis:
            return None

        cache_key = self._cache_key(symbol)
        cached_value = await self._redis.get(cache_key)
        if not cached_value:
            return None

        try:
            cached_data = json.loads(cached_value)
        except json.JSONDecodeError:
            return None

        cached_data["source"] = "cache"
        return cached_data

    async def _set_cached_price(self, symbol: str, payload: Dict[str, object]) -> None:
        if not self._redis:
            return

        cache_key = self._cache_key(symbol)
        await self._redis.set(cache_key, json.dumps(payload), ex=self._cache_ttl)

    def _cache_key(self, symbol: str) -> str:
        return f"crypto:price:{symbol}"

    async def _fetch_price_from_source(
        self, name: str, fetcher, symbol: str
    ) -> Optional[PriceResult]:
        try:
            price = await fetcher(symbol)
            if price is None:
                return None
            if not isinstance(price, (int, float)) or price <= 0:
                return None
            return PriceResult(source=name, price=float(price))
        except (ClientError, asyncio.TimeoutError, KeyError, ValueError) as exc:
            print(f"Error fetching price from {name}: {exc}")
            return None
        except Exception as exc:  # pragma: no cover - safeguard
            print(f"Unexpected error fetching price from {name}: {exc}")
            return None

    async def _request_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict:
        attempt = 0
        delay = self._backoff_base

        while True:
            try:
                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status != 200:
                            raise ValueError(f"Unexpected status {response.status}")
                        return await response.json()
            except (ClientError, asyncio.TimeoutError) as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def coingecko(self, symbol: str) -> float:
        """API Primaria: CoinGecko"""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": symbol.lower(), "vs_currencies": "usd"}
        data = await self._request_json(url, params=params)
        return data[symbol.lower()]["usd"]

    async def binance(self, symbol: str) -> float:
        """API Secundaria: Binance"""
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": f"{symbol}USDT"}
        data = await self._request_json(url, params=params)
        return float(data["price"])

    async def coinmarketcap(self, symbol: str) -> float:
        """API Fallback: CoinMarketCap"""
        if not Config.COINMARKETCAP_API_KEY:
            raise ValueError("CoinMarketCap API key not configured")

        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": Config.COINMARKETCAP_API_KEY}
        params = {"symbol": symbol}
        data = await self._request_json(url, params=params, headers=headers)
        return data["data"][symbol]["quote"]["USD"]["price"]

    def _process_results(self, results: List[object]) -> List[PriceResult]:
        valid_prices: List[PriceResult] = []
        for result in results:
            if isinstance(result, PriceResult):
                valid_prices.append(result)
        return valid_prices

    def _calculate_final_price(self, prices: List[PriceResult]) -> Tuple[float, str]:
        if not prices:
            raise ValueError("No valid prices received")

        sorted_prices = sorted(prices, key=lambda item: item.price)
        median_index = len(sorted_prices) // 2
        median_price = sorted_prices[median_index].price

        if len(sorted_prices) == 1:
            source = sorted_prices[0].source
        else:
            source = "median"

        return median_price, source

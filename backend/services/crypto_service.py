import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

import aiohttp

try:  # pragma: no cover
    from utils.cache import CacheClient
    from utils.config import Config
except ImportError:  # pragma: no cover
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]

LOGGER = logging.getLogger(__name__)
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)

# 🔹 Mapeo de símbolos comunes para CoinGecko
COINGECKO_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "SOL": "solana",
    "DOT": "polkadot",
    "DOGE": "dogecoin",
}


def normalize_symbol(symbol: str) -> dict:
    """
    Normaliza un símbolo tipo 'BTCUSDT' en sus variantes
    para distintos proveedores.
    """
    symbol = symbol.upper()
    base = symbol
    if symbol.endswith("USDT"):
        base = symbol[:-4]  # BTCUSDT -> BTC

    return {
        "binance": symbol,  # Binance usa BTCUSDT directamente
        "coinmarketcap": base,  # CoinMarketCap espera BTC
        "coingecko": COINGECKO_MAP.get(base, base.lower()),  # CoinGecko espera 'bitcoin'
    }


class CryptoService:
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = 0.75

    def __init__(self, cache_client: Optional[CacheClient] = None):
        self.cache = cache_client or CacheClient("crypto-prices", ttl=45)
        self._coingecko_id_cache: Dict[str, Optional[str]] = {}

    async def get_price(self, symbol: str) -> Optional[float]:
        """Obtener precio de un activo crypto con reintentos y fallback."""
        try:
            cache_key = symbol.upper()
            cached_value = await self.cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 🔹 Normalizamos una sola vez
            normalized = normalize_symbol(symbol)

            providers = (
                ("CoinGecko", lambda _: self.coingecko(normalized["coingecko"])),
                ("Binance", lambda _: self.binance(normalized["binance"])),
                ("CoinMarketCap", lambda _: self.coinmarketcap(normalized["coinmarketcap"])),
            )

            for provider_name, provider in providers:
                price = await self._call_with_retries(provider, symbol, provider_name)
                if price is not None:
                    await self.cache.set(cache_key, price)
                    return price

            return None

        except Exception as exc:  # pragma: no cover - errores inesperados
            LOGGER.exception("Error getting crypto price for %s: %s", symbol, exc)
            return None

    async def coingecko(self, coin_id: str) -> Optional[float]:
        """API Primaria: CoinGecko"""
        if not coin_id:
            return None

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}

        try:
            data = await self._request_json(url, params=params)
        except Exception:
            return None

        price = data.get(coin_id, {}).get("usd")
        if isinstance(price, (int, float)):
            return float(price)
        return None

    async def binance(self, symbol: str) -> Optional[float]:
        """API Secundaria: Binance"""
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": symbol}  # 🔹 ahora no agregamos 'USDT' extra

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(url, session=session, params=params)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            LOGGER.error("Error obteniendo precio en Binance para %s: %s", symbol, exc)
            return None

        try:
            return float(data["price"])
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de Binance para %s: %s", symbol, exc)
            return None

    async def coinmarketcap(self, symbol: str) -> Optional[float]:
        """API Fallback: CoinMarketCap"""
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": Config.COINMARKETCAP_API_KEY}
        params = {"symbol": symbol}

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(
                    url, session=session, headers=headers, params=params
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            LOGGER.error("Error obteniendo precio en CoinMarketCap para %s: %s", symbol, exc)
            return None

        try:
            symbol_key = symbol.upper()
            return float(data["data"][symbol_key]["quote"]["USD"]["price"])
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de CoinMarketCap para %s: %s", symbol, exc)
            return None

    async def _request_json(
        self,
        url: str,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        **kwargs,
    ):
        owns_session = session is None
        session = session or aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
        try:
            async with session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            LOGGER.error("Error al solicitar %s: %s", url, exc)
            raise
        finally:
            if owns_session:
                await session.close()

    async def _resolve_coingecko_id(self, symbol: str) -> Optional[str]:
        normalized = symbol.lower()
        if normalized in self._coingecko_id_cache:
            return self._coingecko_id_cache[normalized]

        url = "https://api.coingecko.com/api/v3/search"
        params = {"query": symbol}

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(url, session=session, params=params)
        except Exception:
            self._coingecko_id_cache[normalized] = None
            return None

        for coin in data.get("coins", []):
            if coin.get("symbol", "").lower() == normalized:
                coin_id = coin.get("id")
                self._coingecko_id_cache[normalized] = coin_id
                return coin_id

        self._coingecko_id_cache[normalized] = None
        return None

    async def _call_with_retries(
        self,
        handler: Callable[[str], Awaitable[Optional[float]]],
        symbol: str,
        source_name: str,
    ) -> Optional[float]:
        backoff = self.RETRY_BACKOFF
        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            try:
                result = await handler(symbol)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning(
                    "CryptoService: intento %s fallido con %s para %s: %s",
                    attempt,
                    source_name,
                    symbol,
                    exc,
                )
            else:
                if result is not None:
                    if attempt > 1:
                        LOGGER.info(
                            "CryptoService: %s tuvo éxito para %s tras %s intentos",
                            source_name,
                            symbol,
                            attempt,
                        )
                    return result

                LOGGER.warning(
                    "CryptoService: intento %s no devolvió precio en %s para %s",
                    attempt,
                    source_name,
                    symbol,
                )

            if attempt < self.RETRY_ATTEMPTS:
                await asyncio.sleep(backoff)
                backoff *= 2

        return None

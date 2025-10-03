import asyncio
import logging
from collections.abc import Awaitable, Callable

import aiohttp

try:  # pragma: no cover
    from backend.utils.cache import CacheClient
    from backend.utils.config import Config
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


def normalize_symbol(symbol: str) -> dict[str, str]:
    """
    Normaliza un símbolo tipo 'BTCUSDT' en sus variantes
    para distintos proveedores.
    """
    symbol = symbol.upper()
    base = symbol
    if symbol.endswith("USDT"):
        base = symbol[:-4]  # BTCUSDT -> BTC

    pair = f"{base}/USD"

    return {
        "binance": symbol,  # Binance usa BTCUSDT directamente
        "coinmarketcap": base,  # CoinMarketCap espera BTC
        "coingecko": COINGECKO_MAP.get(
            base, base.lower()
        ),  # CoinGecko espera 'bitcoin'
        "twelvedata": pair,
        "alpha_vantage": base,
    }


class CryptoService:
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = 0.75

    def __init__(self, cache_client: CacheClient | None = None):
        self.cache = cache_client or CacheClient("crypto-prices", ttl=45)
        self._coingecko_id_cache: dict[str, str | None] = {}

    async def get_price(self, symbol: str) -> float | None:
        """Obtener precio de un activo crypto con reintentos y fallback."""
        try:
            cache_key = symbol.upper()
            cached_value = await self.cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 🔹 Normalizamos una sola vez
            normalized = normalize_symbol(symbol)

            providers: tuple[
                tuple[str, Callable[[str], Awaitable[float | None]]], ...
            ] = (
                ("CoinGecko", lambda _: self.coingecko(normalized["coingecko"])),
                ("Binance", lambda _: self.binance(normalized["binance"])),
                (
                    "CoinMarketCap",
                    lambda _: self.coinmarketcap(normalized["coinmarketcap"]),
                ),
                (
                    "TwelveData",
                    lambda _: self.twelvedata(normalized["twelvedata"]),
                ),
                (
                    "AlphaVantage",
                    lambda _: self.alpha_vantage(normalized["alpha_vantage"]),
                ),
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

    async def coingecko(self, coin_id: str) -> float | None:
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
        if isinstance(price, int | float):
            return float(price)
        return None

    async def binance(self, symbol: str) -> float | None:
        """API Secundaria: Binance"""
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": symbol}  # 🔹 ahora no agregamos 'USDT' extra

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(url, session=session, params=params)
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            LOGGER.error("Error obteniendo precio en Binance para %s: %s", symbol, exc)
            return None

        try:
            return float(data["price"])
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de Binance para %s: %s", symbol, exc)
            return None

    async def coinmarketcap(self, symbol: str) -> float | None:
        """API Fallback: CoinMarketCap"""
        if not Config.COINMARKETCAP_API_KEY:
            raise RuntimeError("COINMARKETCAP_API_KEY is not configured")
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": Config.COINMARKETCAP_API_KEY}
        params = {"symbol": symbol}

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(
                    url, session=session, headers=headers, params=params
                )
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            LOGGER.error(
                "Error obteniendo precio en CoinMarketCap para %s: %s", symbol, exc
            )
            return None

        try:
            symbol_key = symbol.upper()
            return float(data["data"][symbol_key]["quote"]["USD"]["price"])
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de CoinMarketCap para %s: %s", symbol, exc)
            return None

    async def twelvedata(self, pair: str) -> float | None:
        """Support crypto pricing using TwelveData when API key is available."""

        if not Config.TWELVEDATA_API_KEY:
            raise RuntimeError("TWELVEDATA_API_KEY is not configured")

        url = "https://api.twelvedata.com/price"
        params = {"symbol": pair, "apikey": Config.TWELVEDATA_API_KEY}

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(url, session=session, params=params)
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            LOGGER.error("Error obteniendo precio en TwelveData para %s: %s", pair, exc)
            return None

        try:
            return float(data["price"])
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de TwelveData para %s: %s", pair, exc)
            return None

    async def alpha_vantage(self, symbol: str) -> float | None:
        """Fallback provider using Alpha Vantage currency exchange endpoint."""

        if not Config.ALPHA_VANTAGE_API_KEY:
            raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured")

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": symbol,
            "to_currency": "USD",
            "apikey": Config.ALPHA_VANTAGE_API_KEY,
        }

        try:
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                data = await self._request_json(url, session=session, params=params)
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            LOGGER.error(
                "Error obteniendo precio en Alpha Vantage para %s: %s", symbol, exc
            )
            return None

        try:
            info = data["Realtime Currency Exchange Rate"]
            price_value = info["5. Exchange Rate"]
            return float(price_value)
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("Respuesta inválida de Alpha Vantage para %s: %s", symbol, exc)
            return None

    async def _request_json(
        self,
        url: str,
        *,
        session: aiohttp.ClientSession | None = None,
        **kwargs,
    ):
        owns_session = session is None
        session = session or aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
        try:
            async with session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            LOGGER.error("Error al solicitar %s: %s", url, exc)
            raise
        finally:
            if owns_session:
                await session.close()

    async def _resolve_coingecko_id(self, symbol: str) -> str | None:
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
        handler: Callable[[str], Awaitable[float | None]],
        symbol: str,
        source_name: str,
    ) -> float | None:
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

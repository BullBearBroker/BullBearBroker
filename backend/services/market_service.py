import asyncio
import base64
import html
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientError

from backend.core.logging_config import get_logger

# Plotly puede no estar disponible en entornos de prueba sin dependencias opcionales.
try:  # pragma: no cover - depende del entorno
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None  # type: ignore[assignment]

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from backend.services.crypto_service import CryptoService
    from backend.services.stock_service import StockService
    from backend.utils.cache import CacheClient
    from backend.utils.config import Config
except ImportError:  # pragma: no cover
    from backend.services.crypto_service import CryptoService  # type: ignore[no-redef]
    from backend.services.stock_service import StockService  # type: ignore[no-redef]
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]

LOGGER = get_logger(module="market_service")
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)


class MarketService:
    def __init__(
        self,
        *,
        crypto_service: CryptoService | None = None,
        stock_service: StockService | None = None,
        news_cache: CacheClient | None = None,
    ) -> None:
        self.crypto_service = crypto_service or CryptoService()
        self.stock_service = stock_service or StockService()
        self.news_cache = news_cache or CacheClient("market-news", ttl=180)
        self.chart_cache = CacheClient("market-chart", ttl=300)
        self.history_cache = CacheClient("market-history", ttl=600)
        self.binance_cache: dict[str, dict[str, Any]] = {}
        self.cache_timeout = 2  # segundos (más rápido para datos en tiempo real)
        self.base_urls = {
            "binance": "https://api.binance.com/api/v3",
            "binance_futures": "https://fapi.binance.com/fapi/v1",
        }
        self.default_stock_watchlist: Sequence[str] = (
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "META",
            "TSLA",
            "NFLX",
        )

    async def get_price_history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        range_: str = "1mo",
    ) -> dict[str, Any]:
        """Obtiene histórico de precios desde Yahoo Finance."""

        cache_key = f"{symbol}:{interval}:{range_}".lower()
        cached = await self.chart_cache.get(cache_key)
        if cached is not None:
            return cached

        yahoo_symbol = self._format_symbol_for_yahoo(symbol)
        params = {"interval": interval, "range": range_}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url, params=params
        ) as response:
            if response.status != 200:
                raise ClientError(
                    f"Yahoo Finance devolvió estado {response.status} para {symbol}"
                )
            payload = await response.json()

        try:
            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result["indicators"]["quote"][0]
            closes = quote.get("close") or []
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Datos históricos no disponibles para {symbol}") from exc

        values: list[dict[str, Any]] = []
        for ts, close in zip(timestamps, closes, strict=False):
            if close is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=UTC)
            values.append({"timestamp": dt.isoformat(), "close": float(close)})

        if not values:
            raise ValueError(f"Sin datos históricos para {symbol}")

        history = {
            "symbol": symbol.upper(),
            "values": values,
            "source": "Yahoo Finance",
        }
        await self.chart_cache.set(cache_key, history)
        return history

    async def get_historical_ohlc(
        self,
        symbol: str,
        *,
        interval: str = "1h",
        limit: int = 300,
        market: str = "auto",
    ) -> dict[str, Any]:
        """Obtener velas OHLC usando proveedores gratuitos y cachearlas."""

        limit = max(10, min(limit, 1000))
        cache_key = f"{symbol}:{interval}:{limit}:{market}".lower()
        cached = await self.history_cache.get(cache_key)
        if cached is not None:
            return cached

        symbol_up = symbol.upper()
        market_mode = market.lower()
        data: dict[str, Any] | None = None
        errors: list[str] = []

        if market_mode in {"auto", "crypto"} and self._looks_like_crypto(symbol_up):
            try:
                data = await self._fetch_binance_history(symbol_up, interval, limit)
            except Exception as exc:  # pragma: no cover - fallback defensivo
                LOGGER.warning(
                    "binance_history_unavailable", symbol=symbol_up, error=str(exc)
                )
                errors.append(f"Binance: {exc}")
                if market_mode == "crypto":
                    raise

        if data is None and market_mode in {"auto", "stock", "equity", "forex"}:
            try:
                data = await self._fetch_yahoo_history(symbol_up, interval, limit)
            except Exception as exc:
                LOGGER.warning(
                    "yahoo_history_unavailable", symbol=symbol_up, error=str(exc)
                )
                errors.append(f"Yahoo: {exc}")

        if data is None:
            detail = "; ".join(errors) if errors else "proveedores sin datos"
            raise ValueError(f"No se encontraron datos históricos para {symbol_up} ({detail})")

        await self.history_cache.set(cache_key, data)
        return data

    async def _fetch_binance_history(
        self, symbol: str, interval: str, limit: int
    ) -> dict[str, Any]:
        allowed = {
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
            "1M",
        }
        if interval not in allowed:
            raise ValueError(f"Intervalo no soportado por Binance: {interval}")

        params = {"symbol": symbol, "interval": interval, "limit": str(limit)}
        url = f"{self.base_urls['binance']}/klines"

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url, params=params
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise ClientError(
                    f"Binance devolvió {response.status} para {symbol}: {text[:120]}"
                )
            payload = await response.json()

        candles: list[dict[str, Any]] = []
        for entry in payload:
            try:
                open_time = int(entry[0]) / 1000
                candles.append(
                    {
                        "timestamp": datetime.fromtimestamp(open_time, tz=UTC).isoformat(),
                        "open": float(entry[1]),
                        "high": float(entry[2]),
                        "low": float(entry[3]),
                        "close": float(entry[4]),
                        "volume": float(entry[5]),
                    }
                )
            except (TypeError, ValueError, IndexError) as exc:
                LOGGER.debug("binance_candle_parse_error", error=str(exc), entry=entry)
                continue

        if not candles:
            raise ValueError(f"Binance no devolvió datos para {symbol}")

        return {
            "symbol": symbol,
            "interval": interval,
            "source": "Binance",
            "values": candles[-limit:],
        }

    async def _fetch_yahoo_history(
        self, symbol: str, interval: str, limit: int
    ) -> dict[str, Any]:
        yahoo_symbol = self._format_symbol_for_yahoo(symbol)
        range_map = {
            "1m": "7d",
            "5m": "1mo",
            "15m": "2mo",
            "30m": "3mo",
            "1h": "3mo",
            "2h": "6mo",
            "4h": "6mo",
            "1d": "max",
            "1w": "max",
            "1mo": "max",
        }
        params = {"interval": interval, "range": range_map.get(interval, "1y")}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url, params=params
        ) as response:
            if response.status != 200:
                raise ClientError(
                    f"Yahoo Finance devolvió estado {response.status} para {symbol}"
                )
            payload = await response.json()

        try:
            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp") or []
            quote = result["indicators"]["quote"][0]
            opens = quote.get("open") or []
            highs = quote.get("high") or []
            lows = quote.get("low") or []
            closes = quote.get("close") or []
            volumes = quote.get("volume") or []
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Datos históricos no disponibles para {symbol}") from exc

        candles: list[dict[str, Any]] = []
        for ts, open_, high, low, close, volume in zip(
            timestamps, opens, highs, lows, closes, volumes, strict=False
        ):
            if None in (open_, high, low, close):
                continue
            dt = datetime.fromtimestamp(ts, tz=UTC)
            candles.append(
                {
                    "timestamp": dt.isoformat(),
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0.0),
                }
            )

        if not candles:
            raise ValueError(f"Sin datos históricos para {symbol}")

        return {
            "symbol": symbol,
            "interval": interval,
            "source": "Yahoo Finance",
            "values": candles[-limit:],
        }

    def _looks_like_crypto(self, symbol: str) -> bool:
        if "/" in symbol:
            symbol = symbol.replace("/", "")
        return any(symbol.endswith(suffix) for suffix in ("USDT", "USDC", "BTC", "ETH"))

    async def get_chart_image(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        range_: str = "1mo",
    ) -> str:
        """Genera un gráfico de precios y devuelve la imagen codificada en base64."""

        history = await self.get_price_history(symbol, interval=interval, range_=range_)
        if go is None:
            raise RuntimeError("Plotly no está disponible para generar gráficos")
        x_values = [item["timestamp"] for item in history["values"]]
        y_values = [item["close"] for item in history["values"]]

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    name=history["symbol"],
                    line=dict(color="#00b894", width=2),
                )
            ]
        )
        fig.update_layout(
            title=f"{history['symbol']} ({interval}, {range_})",
            xaxis_title="Fecha",
            yaxis_title="Precio",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
        )

        image_bytes = fig.to_image(format="png", width=900, height=500, scale=2)
        return base64.b64encode(image_bytes).decode("ascii")

    @staticmethod
    def _format_symbol_for_yahoo(symbol: str) -> str:
        upper = symbol.upper()
        if "/" in upper:
            base, quote = upper.split("/", maxsplit=1)
            return f"{base}{quote}=X"
        if "-" in upper:
            base, quote = upper.split("-", maxsplit=1)
            return f"{base}{quote}=X"
        return upper

    async def get_top_performers(self) -> dict[str, Any]:
        """Obtener los mejores performers del mercado priorizando datos reales."""
        try:
            crypto_data = await self.get_binance_top_performers()
            stock_data = await self.get_stock_market_data()
            if not stock_data and not (
                crypto_data.get("top_gainers") or crypto_data.get("top_losers")
            ):
                raise ValueError("No se pudieron recuperar datos de mercado")
            return await self.process_market_data(stock_data, crypto_data)
        except Exception as exc:
            LOGGER.exception("Error getting real market data: %s", exc)
            return await self.get_simulated_data()

    async def get_crypto_price(self, symbol: str) -> dict[str, Any] | None:
        """Obtiene información de precio para un activo crypto delegando en CryptoService."""
        try:
            crypto_price = await self.crypto_service.get_price(symbol)
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("CryptoService error fetching %s: %s", symbol, exc)
            crypto_price = None

        binance_data = await self.get_binance_price(symbol)
        if crypto_price is None and not binance_data:
            return None

        price = crypto_price
        if price is None and binance_data:
            price = binance_data.get("price")

        if price is None:
            return None

        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "type": "crypto",
            "price": float(price),
            "raw_change": None,
            "high": None,
            "low": None,
            "volume": None,
            "source": "CryptoService" if crypto_price is not None else None,
        }

        if binance_data:
            payload.update(
                {
                    "raw_change": binance_data.get("change"),
                    "high": binance_data.get("high"),
                    "low": binance_data.get("low"),
                    "volume": binance_data.get("volume"),
                }
            )
            binance_source = binance_data.get("source")
            if payload["source"] and binance_source:
                payload["source"] = f"{payload['source']} + {binance_source}"
            elif binance_source:
                payload["source"] = binance_source
            if crypto_price is None and binance_data.get("price") is not None:
                payload["price"] = float(binance_data["price"])

        if payload["source"] is None:
            payload["source"] = "CryptoService"

        return payload

    async def get_stock_price(self, symbol: str) -> dict[str, Any] | None:
        """Obtiene información de precio para un activo bursátil delegando en StockService."""
        try:
            stock_payload = await self.stock_service.get_price(symbol)
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("StockService error fetching %s: %s", symbol, exc)
            return None

        if not stock_payload:
            return None

        change = stock_payload.get("change")
        try:
            raw_change = float(change) if change is not None else None
        except (TypeError, ValueError):
            raw_change = None

        return {
            "symbol": symbol.upper(),
            "type": "stock",
            "price": float(stock_payload["price"]),
            "raw_change": raw_change,
            "high": None,
            "low": None,
            "volume": None,
            "source": stock_payload.get("source", "StockService"),
        }

    async def get_binance_top_performers(self) -> dict[str, list[dict[str, Any]]]:
        """Obtener top performers de Binance."""
        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
                url
            ) as response:
                if response.status != 200:
                    raise ClientError(f"Binance API returned status {response.status}")
                data = await response.json()

            usdt_pairs: list[dict[str, Any]] = []
            for item in data:
                if not item["symbol"].endswith("USDT"):
                    continue
                try:
                    change = float(item["priceChangePercent"])
                    last_price = float(item["lastPrice"])
                    volume = float(item["volume"])
                except (KeyError, TypeError, ValueError):
                    continue
                usdt_pairs.append(
                    {
                        "symbol": item["symbol"].replace("USDT", ""),
                        "price": last_price,
                        "raw_change": change,
                        "volume": volume,
                        "type": "crypto",
                        "source": "Binance",
                    }
                )

            sorted_pairs = sorted(
                usdt_pairs,
                key=lambda x: x["raw_change"],
                reverse=True,
            )

            top_gainers = sorted_pairs[:5]
            top_losers = sorted(
                [item for item in usdt_pairs if item["raw_change"] < 0],
                key=lambda x: x["raw_change"],
            )[:5]

            return {"top_gainers": top_gainers, "top_losers": top_losers}

        except Exception as exc:
            LOGGER.exception("Error getting Binance top performers: %s", exc)
            return {"top_gainers": [], "top_losers": []}

    async def get_binance_price(self, symbol: str) -> dict[str, Any] | None:
        """Obtener precio de Binance con cache."""
        cache_key = f"binance_{symbol.upper()}"
        current_time = time.time()

        cached = self.binance_cache.get(cache_key)
        if cached and current_time - cached["timestamp"] < self.cache_timeout:
            return cached["data"]

        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            params = {"symbol": f"{symbol.upper()}USDT"}

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
                url, params=params
            ) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "Binance API error for %s: Status %s",
                        symbol,
                        response.status,
                    )
                    return None
                data = await response.json()

            price_data = {
                "price": float(data["lastPrice"]),
                "change": float(data.get("priceChangePercent", 0.0)),
                "high": float(data.get("highPrice", 0.0)),
                "low": float(data.get("lowPrice", 0.0)),
                "volume": float(data.get("volume", 0.0)),
                "source": "Binance",
                "timestamp": current_time,
            }

            self.binance_cache[cache_key] = {"data": price_data, "timestamp": current_time}
            return price_data
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("Binance API error for %s: %s", symbol, exc)
            return None

    async def get_binance_orderbook(
        self, symbol: str, limit: int = 10
    ) -> dict[str, Any] | None:
        """Obtener orderbook de Binance."""
        try:
            url = f"{self.base_urls['binance']}/depth"
            params = {"symbol": f"{symbol.upper()}USDT", "limit": limit}

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
                url, params=params
            ) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "Binance orderbook error for %s: Status %s",
                        symbol,
                        response.status,
                    )
                    return None
                data = await response.json()

            return {
                "bids": [
                    [float(price), float(quantity)]
                    for price, quantity in data.get("bids", [])[:limit]
                ],
                "asks": [
                    [float(price), float(quantity)]
                    for price, quantity in data.get("asks", [])[:limit]
                ],
                "lastUpdateId": data.get("lastUpdateId"),
            }
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("Binance orderbook error for %s: %s", symbol, exc)
            return None

    async def get_binance_klines(
        self, symbol: str, interval: str = "1h", limit: int = 24
    ) -> list[dict[str, Any]] | None:
        """Obtener datos de velas (klines) de Binance."""
        try:
            url = f"{self.base_urls['binance']}/klines"
            params = {
                "symbol": f"{symbol.upper()}USDT",
                "interval": interval,
                "limit": limit,
            }

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
                url, params=params
            ) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "Binance klines error for %s: Status %s",
                        symbol,
                        response.status,
                    )
                    return None
                data = await response.json()

            return [
                {
                    "time": kline[0],
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "volume": float(kline[5]),
                }
                for kline in data
            ]
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("Binance klines error for %s: %s", symbol, exc)
            return None

    async def get_price(
        self, symbol: str, asset_type: str | None = None
    ) -> dict[str, Any] | None:
        """Obtener precio de un activo específico usando los nuevos helpers de servicios."""
        try:
            resolved_type = asset_type or await self.detect_asset_type(symbol)
        except Exception as exc:  # pragma: no cover - logging defensivo
            LOGGER.exception("Error detecting asset type for %s: %s", symbol, exc)
            resolved_type = asset_type or "stock"

        if resolved_type == "crypto":
            price_data = await self.get_crypto_price(symbol)
        else:
            price_data = await self.get_stock_price(symbol)

        if not price_data:
            return None

        return {
            "price": self._format_currency(price_data.get("price")),
            "change": self._format_percent(price_data.get("raw_change")),
            "high": self._format_currency(price_data.get("high")),
            "low": self._format_currency(price_data.get("low")),
            "volume": self._format_volume(price_data.get("volume")),
            "raw_price": price_data.get("price"),
            "raw_change": price_data.get("raw_change"),
            "source": price_data.get("source", "Unknown"),
        }

    async def get_stock_market_data(
        self, symbols: Sequence[str] | None = None
    ) -> list[dict[str, Any]]:
        """Obtiene información de un conjunto de símbolos bursátiles usando StockService."""
        tickers = tuple(symbols or self.default_stock_watchlist)
        if not tickers:
            return []

        tasks = [self.get_stock_price(symbol) for symbol in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data: list[dict[str, Any]] = []
        for symbol, result in zip(tickers, results, strict=False):
            if isinstance(result, Exception):
                LOGGER.error("Error fetching stock price for %s: %s", symbol, result)
                continue
            if not result:
                continue
            data.append(result)
        return data

    async def get_crypto_market_data(
        self, symbols: Sequence[str] | None = None
    ) -> list[dict[str, Any]]:
        """Obtiene información crypto adicional usando los nuevos helpers."""
        if not symbols:
            return []

        tasks = [self.get_crypto_price(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data: list[dict[str, Any]] = []
        for symbol, result in zip(symbols, results, strict=False):
            if isinstance(result, Exception):
                LOGGER.error("Error fetching crypto price for %s: %s", symbol, result)
                continue
            if not result:
                continue
            data.append(result)
        return data

    async def process_market_data(
        self,
        stock_data: list[dict[str, Any]],
        crypto_data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Procesar datos de mercado con información real disponible."""
        crypto_gainers = [
            self._format_performer(item)
            for item in crypto_data.get("top_gainers", [])
        ]
        crypto_losers = [
            self._format_performer(item)
            for item in crypto_data.get("top_losers", [])
        ]

        stocks_with_change = [
            item for item in stock_data if item.get("raw_change") is not None
        ]
        stock_top: list[dict[str, Any]] = []
        stock_bottom: list[dict[str, Any]] = []
        if stocks_with_change:
            sorted_stocks = sorted(
                stocks_with_change, key=lambda x: x["raw_change"], reverse=True
            )
            stock_top = [self._format_performer(item) for item in sorted_stocks[:5]]
            stock_bottom = [
                self._format_performer(item)
                for item in sorted(stocks_with_change, key=lambda x: x["raw_change"])[
                    :5
                ]
            ]

        top_performers = self._combine_ranked_lists(
            [crypto_gainers, stock_top], limit=5
        )
        worst_performers = self._combine_ranked_lists(
            [crypto_losers, stock_bottom], limit=5
        )

        if not top_performers and not worst_performers:
            return await self.get_simulated_data()

        market_summary = self._build_market_summary(stock_data, crypto_data)

        return {
            "top_performers": top_performers[:5],
            "worst_performers": worst_performers[:5],
            "market_summary": market_summary,
        }

    async def get_news(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Obtiene noticias relevantes para un símbolo con caché y múltiples fuentes."""
        cache_key = f"{symbol.upper()}:{limit}"
        cached = await self.news_cache.get(cache_key)
        if cached is not None:
            return cached

        articles: list[dict[str, Any]] = []

        if Config.NEWSAPI_API_KEY:
            try:
                articles = await self._fetch_newsapi(symbol, limit)
            except Exception as exc:  # pragma: no cover - logging defensivo
                LOGGER.exception("NewsAPI error for %s: %s", symbol, exc)
                articles = []

        if not articles and getattr(Config, "MEDIASTACK_API_KEY", None):
            try:
                articles = await self._fetch_mediastack(symbol, limit)
            except Exception as exc:  # pragma: no cover - logging defensivo
                LOGGER.exception("MediaStack error for %s: %s", symbol, exc)
                articles = []

        if not articles:
            try:
                articles = await self._fetch_rss(symbol, limit)
            except Exception as exc:  # pragma: no cover - logging defensivo
                LOGGER.exception("RSS error for %s: %s", symbol, exc)
                articles = []

        normalized = [
            {
                "symbol": symbol.upper(),
                "title": item.get("title", "Sin título"),
                "url": item.get("url"),
                "source": item.get("source", "Unknown"),
                "published_at": item.get("published_at"),
                "summary": item.get("summary", ""),
            }
            for item in articles[:limit]
        ]

        await self.news_cache.set(cache_key, normalized, ttl=120)
        return normalized

    async def detect_asset_type(self, symbol: str) -> str:
        """Detectar tipo de activo automáticamente."""
        crypto_symbols = {
            "BTC",
            "ETH",
            "BNB",
            "XRP",
            "ADA",
            "DOGE",
            "SOL",
            "DOT",
            "AVAX",
            "MATIC",
            "LTC",
            "LINK",
            "UNI",
            "ATOM",
            "ETC",
            "XLM",
            "BCH",
            "VET",
            "TRX",
            "FIL",
        }
        return "crypto" if symbol.upper() in crypto_symbols else "stock"

    async def get_simulated_data(self) -> dict[str, Any]:
        """Fallback sin datos sintéticos para evitar métricas artificiadas."""
        # Ajuste: en lugar de devolver precios ficticios dejamos la estructura vacía
        # para garantizar que el cliente sepa que las fuentes externas fallaron.
        return {
            "top_performers": [],
            "worst_performers": [],
            "market_summary": {
                "note": "Fuentes externas no disponibles; se omite data simulada.",
            },
        }

    async def close(self) -> None:
        """Cerrar conexiones (placeholder para compatibilidad)."""

    def _combine_ranked_lists(
        self, sources: Sequence[list[dict[str, Any]]], limit: int
    ) -> list[dict[str, Any]]:
        combined: list[dict[str, Any]] = []
        indices = [0] * len(sources)
        while len(combined) < limit:
            progressed = False
            for idx, items in enumerate(sources):
                pointer = indices[idx]
                if pointer < len(items):
                    combined.append(items[pointer])
                    indices[idx] += 1
                    progressed = True
                    if len(combined) >= limit:
                        break
            if not progressed:
                break
        return combined

    def _format_performer(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": item.get("symbol", ""),
            "price": self._format_currency(item.get("price")),
            "change": self._format_percent(item.get("raw_change")),
            "type": item.get("type", "unknown"),
            "source": item.get("source", "Unknown"),
        }

    def _format_currency(self, value: float | None) -> str:
        if value is None or not isinstance(value, int | float):
            return "N/A"
        return f"${value:,.2f}"

    def _format_percent(self, value: float | None) -> str:
        if value is None or not isinstance(value, int | float):
            return "N/A"
        return f"{value:+.2f}%"

    def _format_volume(self, value: float | None) -> str:
        if value is None or not isinstance(value, int | float):
            return "N/A"
        return f"{value:,.0f}"

    def _build_market_summary(
        self,
        stock_data: list[dict[str, Any]],
        crypto_data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "stocks_covered": len(stock_data),
            "crypto_pairs": len(crypto_data.get("top_gainers", []))
            + len(crypto_data.get("top_losers", [])),
        }

        stocks_with_change = [
            item["raw_change"]
            for item in stock_data
            if isinstance(item.get("raw_change"), int | float)
        ]
        if stocks_with_change:
            avg_change = sum(stocks_with_change) / len(stocks_with_change)
            summary["avg_stock_change"] = self._format_percent(avg_change)

        top_crypto = crypto_data.get("top_gainers", [])
        if top_crypto:
            best = max(
                top_crypto,
                key=lambda x: x.get("raw_change", float("-inf")),
            )
            summary["best_crypto"] = {
                "symbol": best.get("symbol"),
                "change": self._format_percent(best.get("raw_change")),
            }

        return summary

    async def _fetch_newsapi(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        url = "https://newsapi.org/v2/everything"
        headers = {"Authorization": f"Bearer {Config.NEWSAPI_API_KEY}"}
        params = {
            "q": symbol,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
        }

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url, params=params, headers=headers
        ) as response:
            if response.status != 200:
                LOGGER.warning(
                    "NewsAPI returned status %s for %s",
                    response.status,
                    symbol,
                )
                return []
            payload = await response.json()

        articles: list[dict[str, Any]] = []
        for article in payload.get("articles", []):
            source_info = article.get("source") or {}
            articles.append(
                {
                    "title": article.get("title") or article.get("description") or "Sin título",
                    "url": article.get("url"),
                    "source": source_info.get("name") or "NewsAPI",
                    "published_at": self._normalize_datetime(article.get("publishedAt")),
                    "summary": self._clean_html(
                        article.get("description") or article.get("content") or ""
                    ),
                }
            )
        return articles

    async def _fetch_mediastack(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        url = "http://api.mediastack.com/v1/news"
        params = {
            "access_key": Config.MEDIASTACK_API_KEY,
            "keywords": symbol,
            "limit": limit,
            "sort": "published_desc",
            "languages": "en",
        }

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url, params=params
        ) as response:
            if response.status != 200:
                LOGGER.warning(
                    "MediaStack returned status %s for %s",
                    response.status,
                    symbol,
                )
                return []
            payload = await response.json()

        articles: list[dict[str, Any]] = []
        for article in payload.get("data", []):
            articles.append(
                {
                    "title": article.get("title") or "Sin título",
                    "url": article.get("url"),
                    "source": article.get("source") or "MediaStack",
                    "published_at": self._normalize_datetime(article.get("published_at")),
                    "summary": self._clean_html(article.get("description") or ""),
                }
            )
        return articles

    async def _fetch_rss(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        query = f"{symbol} stock"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session, session.get(
            url
        ) as response:
            if response.status != 200:
                LOGGER.warning(
                    "RSS feed returned status %s for %s",
                    response.status,
                    symbol,
                )
                return []
            text = await response.text()

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            LOGGER.warning("Failed to parse RSS feed for %s: %s", symbol, exc)
            return []

        articles: list[dict[str, Any]] = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title") or "Sin título"
            link = item.findtext("link")
            pub_date = item.findtext("pubDate")
            description = item.findtext("description") or ""
            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": self._extract_domain(link),
                    "published_at": self._normalize_datetime(pub_date),
                    "summary": self._clean_html(description),
                }
            )
        return articles

    def _normalize_datetime(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()

    def _clean_html(self, text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", text or "")
        return html.unescape(cleaned).strip()

    def _extract_domain(self, url: str | None) -> str:
        if not url:
            return "Unknown"
        try:
            return urlparse(url).netloc or "Unknown"
        except ValueError:
            return "Unknown"


market_service = MarketService()

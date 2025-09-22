import asyncio
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientError

from services.crypto_service import CryptoService
from services.stock_service import StockService
from utils.cache import CacheClient
from utils.config import Config

LOGGER = logging.getLogger(__name__)
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)


class MarketService:
    def __init__(
        self,
        *,
        crypto_service: Optional[CryptoService] = None,
        stock_service: Optional[StockService] = None,
        news_cache: Optional[CacheClient] = None,
    ) -> None:
        self.crypto_service = crypto_service or CryptoService()
        self.stock_service = stock_service or StockService()
        self.news_cache = news_cache or CacheClient("market-news", ttl=180)
        self.binance_cache: Dict[str, Dict[str, Any]] = {}
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

    async def get_top_performers(self) -> Dict[str, Any]:
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

    async def get_crypto_price(self, symbol: str) -> Optional[Dict[str, Any]]:
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

        payload: Dict[str, Any] = {
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

    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
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

    async def get_binance_top_performers(self) -> Dict[str, List[Dict[str, Any]]]:
        """Obtener top performers de Binance."""
        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ClientError(
                            f"Binance API returned status {response.status}"
                        )
                    data = await response.json()

            usdt_pairs: List[Dict[str, Any]] = []
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

    async def get_binance_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obtener precio de Binance con cache."""
        cache_key = f"binance_{symbol.upper()}"
        current_time = time.time()

        cached = self.binance_cache.get(cache_key)
        if cached and current_time - cached["timestamp"] < self.cache_timeout:
            return cached["data"]

        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            params = {"symbol": f"{symbol.upper()}USDT"}

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                async with session.get(url, params=params) as response:
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
    ) -> Optional[Dict[str, Any]]:
        """Obtener orderbook de Binance."""
        try:
            url = f"{self.base_urls['binance']}/depth"
            params = {"symbol": f"{symbol.upper()}USDT", "limit": limit}

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                async with session.get(url, params=params) as response:
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
    ) -> Optional[List[Dict[str, Any]]]:
        """Obtener datos de velas (klines) de Binance."""
        try:
            url = f"{self.base_urls['binance']}/klines"
            params = {
                "symbol": f"{symbol.upper()}USDT",
                "interval": interval,
                "limit": limit,
            }

            async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
                async with session.get(url, params=params) as response:
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
        self, symbol: str, asset_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
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
        self, symbols: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene información de un conjunto de símbolos bursátiles usando StockService."""
        tickers = tuple(symbols or self.default_stock_watchlist)
        if not tickers:
            return []

        tasks = [self.get_stock_price(symbol) for symbol in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data: List[Dict[str, Any]] = []
        for symbol, result in zip(tickers, results):
            if isinstance(result, Exception):
                LOGGER.error("Error fetching stock price for %s: %s", symbol, result)
                continue
            if not result:
                continue
            data.append(result)
        return data

    async def get_crypto_market_data(
        self, symbols: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene información crypto adicional usando los nuevos helpers."""
        if not symbols:
            return []

        tasks = [self.get_crypto_price(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data: List[Dict[str, Any]] = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                LOGGER.error("Error fetching crypto price for %s: %s", symbol, result)
                continue
            if not result:
                continue
            data.append(result)
        return data

    async def process_market_data(
        self,
        stock_data: List[Dict[str, Any]],
        crypto_data: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
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
        stock_top: List[Dict[str, Any]] = []
        stock_bottom: List[Dict[str, Any]] = []
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

    async def get_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene noticias relevantes para un símbolo con caché y múltiples fuentes."""
        cache_key = f"{symbol.upper()}:{limit}"
        cached = await self.news_cache.get(cache_key)
        if cached is not None:
            return cached

        articles: List[Dict[str, Any]] = []

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

    async def get_simulated_data(self) -> Dict[str, Any]:
        """Datos simulados de respaldo cuando las fuentes externas fallan."""
        return {
            "top_performers": [
                {
                    "symbol": "BTC",
                    "price": "$45,123.45",
                    "change": "+2.5%",
                    "type": "crypto",
                },
                {
                    "symbol": "ETH",
                    "price": "$2,567.89",
                    "change": "+1.8%",
                    "type": "crypto",
                },
                {
                    "symbol": "AAPL",
                    "price": "$178.90",
                    "change": "+0.7%",
                    "type": "stock",
                },
                {
                    "symbol": "MSFT",
                    "price": "$345.21",
                    "change": "+0.3%",
                    "type": "stock",
                },
                {
                    "symbol": "SOL",
                    "price": "$95.67",
                    "change": "+1.2%",
                    "type": "crypto",
                },
            ],
            "worst_performers": [
                {
                    "symbol": "TSLA",
                    "price": "$245.67",
                    "change": "-0.8%",
                    "type": "stock",
                },
                {
                    "symbol": "XRP",
                    "price": "$0.58",
                    "change": "-0.3%",
                    "type": "crypto",
                },
                {
                    "symbol": "NFLX",
                    "price": "$567.89",
                    "change": "-0.5%",
                    "type": "stock",
                },
                {
                    "symbol": "DOGE",
                    "price": "$0.12",
                    "change": "-0.2%",
                    "type": "crypto",
                },
                {
                    "symbol": "ADA",
                    "price": "$0.45",
                    "change": "-0.1%",
                    "type": "crypto",
                },
            ],
            "market_summary": {
                "note": "Datos simulados utilizados como fallback",
            },
        }

    async def close(self) -> None:
        """Cerrar conexiones (placeholder para compatibilidad)."""
        pass

    def _combine_ranked_lists(
        self, sources: Sequence[List[Dict[str, Any]]], limit: int
    ) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
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

    def _format_performer(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": item.get("symbol", ""),
            "price": self._format_currency(item.get("price")),
            "change": self._format_percent(item.get("raw_change")),
            "type": item.get("type", "unknown"),
            "source": item.get("source", "Unknown"),
        }

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None or not isinstance(value, (int, float)):
            return "N/A"
        return f"${value:,.2f}"

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None or not isinstance(value, (int, float)):
            return "N/A"
        return f"{value:+.2f}%"

    def _format_volume(self, value: Optional[float]) -> str:
        if value is None or not isinstance(value, (int, float)):
            return "N/A"
        return f"{value:,.0f}"

    def _build_market_summary(
        self,
        stock_data: List[Dict[str, Any]],
        crypto_data: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stocks_covered": len(stock_data),
            "crypto_pairs": len(crypto_data.get("top_gainers", []))
            + len(crypto_data.get("top_losers", [])),
        }

        stocks_with_change = [
            item["raw_change"]
            for item in stock_data
            if isinstance(item.get("raw_change"), (int, float))
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

    async def _fetch_newsapi(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        url = "https://newsapi.org/v2/everything"
        headers = {"Authorization": f"Bearer {Config.NEWSAPI_API_KEY}"}
        params = {
            "q": symbol,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
        }

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "NewsAPI returned status %s for %s",
                        response.status,
                        symbol,
                    )
                    return []
                payload = await response.json()

        articles: List[Dict[str, Any]] = []
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

    async def _fetch_mediastack(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        url = "http://api.mediastack.com/v1/news"
        params = {
            "access_key": Config.MEDIASTACK_API_KEY,
            "keywords": symbol,
            "limit": limit,
            "sort": "published_desc",
            "languages": "en",
        }

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    LOGGER.warning(
                        "MediaStack returned status %s for %s",
                        response.status,
                        symbol,
                    )
                    return []
                payload = await response.json()

        articles: List[Dict[str, Any]] = []
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

    async def _fetch_rss(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        query = f"{symbol} stock"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        async with aiohttp.ClientSession(timeout=CLIENT_TIMEOUT) as session:
            async with session.get(url) as response:
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

        articles: List[Dict[str, Any]] = []
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

    def _normalize_datetime(self, value: Optional[str]) -> Optional[str]:
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
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    def _clean_html(self, text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", text or "")
        return html.unescape(cleaned).strip()

    def _extract_domain(self, url: Optional[str]) -> str:
        if not url:
            return "Unknown"
        try:
            return urlparse(url).netloc or "Unknown"
        except ValueError:
            return "Unknown"


market_service = MarketService()

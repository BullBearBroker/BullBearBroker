"""Servicio de agregación de sentimiento del mercado."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

import aiohttp

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from utils.cache import CacheClient
    from utils.config import Config
except ImportError:  # pragma: no cover
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]

FNG_API_URL = "https://api.alternative.me/fng/"


class SentimentService:
    """Combina indicadores de sentimiento de diversas fuentes."""

    def __init__(
        self,
        *,
        market_cache: Optional[CacheClient] = None,
        text_cache: Optional[CacheClient] = None,
        session_factory=aiohttp.ClientSession,
    ) -> None:
        self.market_cache = market_cache or CacheClient("fear-greed", ttl=300)
        self.text_cache = text_cache or CacheClient("sentiment-text", ttl=120)
        self._session_factory = session_factory
        self._timeout = aiohttp.ClientTimeout(total=10)

    async def get_market_sentiment(self) -> Optional[Dict[str, Any]]:
        """Obtiene el índice Fear & Greed de Alternative.me."""

        cached = await self.market_cache.get("fear-greed")
        if cached is not None:
            return cached

        async with self._session_factory(timeout=self._timeout) as session:
            async with session.get(FNG_API_URL) as response:
                if response.status >= 400:
                    return None
                data = await response.json()

        payload = {
            "value": data.get("data", [{}])[0].get("value"),
            "classification": data.get("data", [{}])[0].get("value_classification"),
            "timestamp": data.get("data", [{}])[0].get("timestamp"),
        }
        await self.market_cache.set("fear-greed", payload)
        return payload

    async def analyze_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Analiza texto usando el modelo de HuggingFace configurado."""

        normalized = text.strip()
        if not normalized:
            return None

        cache_key = normalized.lower()
        cached = await self.text_cache.get(cache_key)
        if cached is not None:
            return cached

        headers = {"Content-Type": "application/json"}
        if Config.HUGGINGFACE_API_TOKEN:
            headers["Authorization"] = f"Bearer {Config.HUGGINGFACE_API_TOKEN}"

        payload = json.dumps({"inputs": normalized})
        url = f"{Config.HUGGINGFACE_API_URL}/{Config.HUGGINGFACE_SENTIMENT_MODEL}"

        async with self._session_factory(timeout=self._timeout) as session:
            async with session.post(url, data=payload, headers=headers) as response:
                if response.status >= 400:
                    return None
                data = await response.json()

        if isinstance(data, list) and data:
            candidate = data[0]
            if isinstance(candidate, list) and candidate:
                sentiment = candidate[0]
            else:
                sentiment = candidate
        elif isinstance(data, dict) and "label" in data:
            sentiment = data
        else:
            sentiment = None

        if sentiment is None:
            return None

        result = {
            "label": sentiment.get("label"),
            "score": sentiment.get("score"),
            "model": Config.HUGGINGFACE_SENTIMENT_MODEL,
        }
        await self.text_cache.set(cache_key, result)
        return result

    async def get_sentiment(
        self, symbol: str, *, text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Devuelve la información de sentimiento para ``symbol``."""

        market = await self.get_market_sentiment()
        text_target = text or symbol.upper()
        text_sentiment = await self.analyze_text(text_target)
        return {
            "symbol": symbol.upper(),
            "market_sentiment": market,
            "text_sentiment": text_sentiment,
        }


sentiment_service = SentimentService()

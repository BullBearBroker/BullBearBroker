from __future__ import annotations

from typing import Any, Dict, Optional

import aiohttp

from utils.config import Config


class SentimentService:
    """Integración con Alternative.me y HuggingFace para sentimiento de mercado."""

    _ALTERNATIVE_API_URL = "https://api.alternative.me/fng/"

    def __init__(self) -> None:
        self._hf_token = Config.HUGGINGFACE_API_TOKEN
        self._hf_model = Config.HUGGINGFACE_MODEL
        self._timeout = aiohttp.ClientTimeout(total=30)

    async def get_fear_and_greed_index(self) -> Dict[str, Any]:
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(self._ALTERNATIVE_API_URL) as response:
                if response.status != 200:
                    raise RuntimeError(f"Alternative.me devolvió estado {response.status}")
                payload = await response.json()
                data = (payload.get("data") or [None])[0]
                if not data:
                    raise RuntimeError(f"Respuesta inesperada de Alternative.me: {payload}")
                return {
                    "value": int(data.get("value")),
                    "classification": data.get("value_classification"),
                    "timestamp": data.get("timestamp"),
                    "time_until_update": payload.get("metadata", {}).get("time_until_update"),
                }

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        if not text.strip():
            raise ValueError("El texto a analizar no puede estar vacío")
        if not self._hf_token:
            return {
                "provider": "huggingface",
                "model": self._hf_model,
                "detail": "HUGGINGFACE_API_TOKEN no configurado",
                "results": [],
            }

        headers = {"Authorization": f"Bearer {self._hf_token}"}
        payload = {"inputs": text}
        endpoint = f"https://api-inference.huggingface.co/models/{self._hf_model}"

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                if response.status == 503:
                    # modelo cargándose
                    return {
                        "provider": "huggingface",
                        "model": self._hf_model,
                        "detail": "Modelo en proceso de carga, intenta nuevamente en unos segundos",
                        "results": [],
                    }
                if response.status >= 400:
                    raise RuntimeError(f"HuggingFace devolvió estado {response.status}")
                results = await response.json()
                return {
                    "provider": "huggingface",
                    "model": self._hf_model,
                    "results": results,
                }

    async def get_market_sentiment(self, context_text: Optional[str] = None) -> Dict[str, Any]:
        fear_greed = await self.get_fear_and_greed_index()
        text_sentiment: Optional[Dict[str, Any]] = None
        if context_text:
            text_sentiment = await self.analyze_text(context_text)
        return {
            "fear_and_greed": fear_greed,
            "text_sentiment": text_sentiment,
        }


sentiment_service = SentimentService()

import asyncio
import logging
from typing import Any, Dict

import aiohttp

from utils.config import Config


logger = logging.getLogger(__name__)


class HuggingFaceService:
    """Cliente asíncrono para el endpoint de chat de HuggingFace."""

    def __init__(self) -> None:
        self.api_key = Config.HF_API_KEY
        self.base_url = "https://api-inference.huggingface.co/v1/chat/completions"
        self.model = "meta-llama/Meta-Llama-3-8B-Instruct"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def configure(self, api_key: str) -> None:
        """Permite ajustar la API key dinámicamente (útil en pruebas)."""
        self.api_key = api_key

    async def generate_financial_response(self, user_message: str, context: Dict[str, Any] | None = None) -> str:
        if not self.is_configured:
            raise RuntimeError("HuggingFace API key no configurada")

        system_prompt = self._create_system_prompt(context)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        raise RuntimeError(
                            f"HuggingFace devolvió código {response.status}: {error_detail}"
                        )

                    data = await response.json()
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Timeout al solicitar respuesta a HuggingFace") from exc
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Error de conexión con HuggingFace: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Formato de respuesta inesperado de HuggingFace") from exc

        if not content or not content.strip():
            raise RuntimeError("Respuesta vacía de HuggingFace")

        logger.debug("Respuesta obtenida de HuggingFace")
        return content

    def _create_system_prompt(self, context: Dict[str, Any] | None = None) -> str:
        base_prompt = """Eres BullBearBroker, un asistente financiero profesional.
Proporciona análisis de mercados (acciones, cripto, forex) con un tono claro y responsable.
Incluye advertencias de riesgo cuando sea pertinente y datos concretos cuando estén disponibles."""

        if not context:
            return base_prompt

        context_lines = []
        market_data = context.get("market_data")
        if market_data:
            context_lines.append(f"Datos de mercado: {market_data}")

        user_portfolio = context.get("user_portfolio")
        if user_portfolio:
            context_lines.append(f"Portfolio usuario: {user_portfolio}")

        if context_lines:
            return base_prompt + "\nContexto adicional:\n" + "\n".join(context_lines)

        return base_prompt


huggingface_service = HuggingFaceService()

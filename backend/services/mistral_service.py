import asyncio
import json
import logging
import os
from collections import defaultdict
from typing import Any

import aiohttp
from dotenv import load_dotenv

load_dotenv()


logger = logging.getLogger(__name__)


class MistralAPIError(Exception):
    """Exception raised when the Mistral API returns an error response."""

    def __init__(self, status: int | None, body: str, model: str):
        self.status = status
        self.body = body
        self.model = model
        message = f"Mistral API error ({status}) on model {model}: {body}"
        super().__init__(message)


class MistralService:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1"
        self.models = {
            "small": "mistral-small-latest",
            "medium": "mistral-medium-latest",
            "large": "mistral-large-latest",
        }
        self.max_retries = 3
        self.initial_backoff = 1
        self.retryable_statuses = {429} | set(range(500, 600))
        self.metrics = {"attempts": 0, "model_attempts": defaultdict(int)}

    async def chat_completion(
        self, messages: list, model: str = "medium"
    ) -> str | None:
        """
        Enviar mensajes a Mistral AI y obtener respuesta
        """
        if not self.api_key:
            raise ValueError("Mistral API key no configurada")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        models_to_try = self._build_model_fallback(model)

        last_error: MistralAPIError | None = None

        try:
            async with aiohttp.ClientSession() as session:
                for model_name in models_to_try:
                    try:
                        return await self._attempt_model(
                            session=session,
                            headers=headers,
                            messages=messages,
                            model_name=model_name,
                        )
                    except TimeoutError:
                        logger.error(
                            "Timeout while calling Mistral model %s", model_name
                        )
                        raise
                    except MistralAPIError as exc:
                        last_error = exc
                        if exc.status not in self.retryable_statuses:
                            raise
                        logger.warning(str(exc))
                        continue
        except aiohttp.ClientError as exc:
            logger.error("Client error while calling Mistral AI: %s", exc)
        except Exception:
            logger.exception("Unexpected error while calling Mistral AI")

        if last_error:
            raise last_error

        return None

    def _build_model_fallback(self, preferred: str) -> list[str]:
        ordered_models = ["medium", "small", "large"]
        fallback = [preferred] if preferred in ordered_models else []
        fallback.extend(model for model in ordered_models if model not in fallback)
        return fallback

    async def _attempt_model(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        messages: list,
        model_name: str,
    ) -> str:
        payload = {
            "model": self.models[model_name],
            "messages": messages,
            "temperature": 0.1,  # Baja temperatura para respuestas precisas
            "max_tokens": 1000,
        }

        backoff = self.initial_backoff
        last_error: MistralAPIError | None = None

        for attempt in range(1, self.max_retries + 1):
            self.metrics["attempts"] += 1
            self.metrics["model_attempts"][model_name] += 1
            try:
                data = await self._perform_request(session, headers, payload)
                return data["choices"][0]["message"]["content"]
            except TimeoutError:
                raise
            except MistralAPIError as exc:
                last_error = exc
                if exc.status not in self.retryable_statuses:
                    raise
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(backoff)
                backoff *= 2

        if last_error:
            raise last_error
        raise MistralAPIError(None, "Unknown error", payload["model"])

    async def _perform_request(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        async with session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        ) as response:
            if response.status == 200:
                return await response.json()

            error_body = await response.text()
            if 400 <= response.status < 600:
                raise MistralAPIError(response.status, error_body, payload["model"])

            raise MistralAPIError(response.status, error_body, payload["model"])

    def get_metrics(self) -> dict[str, Any]:
        return {
            "attempts": self.metrics["attempts"],
            "model_attempts": dict(self.metrics["model_attempts"]),
        }

    async def generate_financial_response(
        self, user_message: str, context: dict[str, Any] | None = None
    ) -> str:
        """
        Generar respuesta especializada en finanzas
        """
        # Preparar el contexto del sistema
        system_prompt = self._create_system_prompt(context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.chat_completion(messages, model="medium")
        except (TimeoutError, MistralAPIError) as exc:
            logger.error("Error generating financial response: %s", exc)
            return (
                "Lo siento, estoy teniendo dificultades para procesar tu solicitud. "
                "Por favor intenta nuevamente."
            )

        if not response:
            return (
                "Lo siento, estoy teniendo dificultades para procesar tu solicitud. "
                "Por favor intenta nuevamente."
            )

        return response

    def _create_system_prompt(self, context: dict[str, Any] = None) -> str:
        """
        Crear prompt del sistema especializado en finanzas
        """
        base_prompt = (
            "Eres BullBearBroker, un asistente de IA especializado en mercados financieros. "
            "Tu expertise incluye: acciones, criptomonedas, forex, análisis técnico "
            "y fundamental.\n\n"
            "Reglas importantes:\n"
            "1. Sé preciso y basado en datos reales\n"
            "2. Proporciona análisis objetivos sin bias emocional\n"
            "3. Incluye datos concretos cuando sea posible\n"
            "4. Advierte sobre riesgos cuando sea apropiado\n"
            "5. Mantén un tono profesional pero accesible\n\n"
            "Formato de respuestas:\n"
            "- Incluye emojis relevantes (📈, ₿, 🔍)\n"
            "- Usa negritas para puntos importantes\n"
            "- Proporciona insights accionables\n"
            "- Sé conciso pero completo"
        )

        if context:
            # Agregar contexto específico si está disponible
            context_str = "\nContexto adicional:\n"
            if "market_data" in context:
                context_str += f"Datos de mercado: {context['market_data']}\n"
            if "user_portfolio" in context:
                context_str += f"Portfolio usuario: {context['user_portfolio']}\n"

            return base_prompt + context_str

        return base_prompt

    async def analyze_market_sentiment(self, news_text: str) -> dict[str, float]:
        """
        Analizar sentimiento de noticias financieras
        """
        prompt = f"""
        Analiza el sentimiento de esta noticia financiera y devuelve SOLO un JSON con:
        - sentiment_score: float entre -1 (muy negativo) y 1 (muy positivo)
        - confidence: float entre 0 y 1
        - keywords: array de palabras clave importantes

        Noticia: {news_text[:1000]}  # Limitar longitud
        """

        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un analista de sentimiento financiero. Devuelve SOLO JSON válido."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.chat_completion(messages, model="small")
        except (TimeoutError, MistralAPIError) as exc:
            logger.error("Error analyzing market sentiment: %s", exc)
            return {"sentiment_score": 0.0, "confidence": 0.0, "keywords": []}

        try:
            if response:
                return json.loads(response.strip())
        except Exception:
            pass

        return {"sentiment_score": 0.0, "confidence": 0.0, "keywords": []}


# Singleton instance
mistral_service = MistralService()

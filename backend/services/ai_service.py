import asyncio
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Tuple

import aiohttp

from .huggingface_service import huggingface_service
from .mistral_service import mistral_service


logger = logging.getLogger(__name__)


ProviderHandler = Callable[[str, Dict[str, Any]], Awaitable[str]]


class AIService:
    def __init__(self) -> None:
        self.market_service = None
        self.max_retries = 3
        self._ollama_base_url = "http://127.0.0.1:11434"
        self._ollama_model = "llama3"
        self._ollama_cache: Dict[str, Any] = {"available": False, "checked_at": 0.0}
        self._ollama_cache_ttl = 60

    def set_market_service(self, market_service) -> None:
        self.market_service = market_service

    async def process_message(self, message: str, context: Dict[str, Any] | None = None) -> str:
        """Procesar mensaje del usuario y generar respuesta."""
        prepared_context = await self._prepare_context(message, context)
        provider_pipeline = await self._get_provider_pipeline()
        errors: List[str] = []

        for provider_name, handler in provider_pipeline:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await handler(message, prepared_context)
                    if not response or not response.strip():
                        raise RuntimeError(f"{provider_name} devolvió una respuesta vacía")

                    logger.info(
                        "Respuesta generada con %s en el intento %d", provider_name, attempt
                    )
                    return response
                except Exception as exc:  # noqa: BLE001 - queremos registrar cualquier fallo
                    error_message = f"{provider_name} intento {attempt}: {exc}"
                    errors.append(error_message)
                    logger.warning(
                        "Fallo proveedor %s en intento %d: %s", provider_name, attempt, exc
                    )

                    if attempt < self.max_retries:
                        await asyncio.sleep(self._calculate_backoff(attempt))
                    else:
                        break

        if errors:
            logger.error(
                "Todos los proveedores fallaron. Se utilizará la respuesta local. Detalles: %s",
                "; ".join(errors),
            )
        else:
            logger.error("No se encontraron proveedores de IA disponibles. Se usa fallback local.")

        return await self.generate_response(message)

    async def _prepare_context(
        self, message: str, context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        context_data: Dict[str, Any] = dict(context or {})
        market_context = await self.get_market_context(message)
        context_data.update(market_context)
        return context_data

    async def _get_provider_pipeline(self) -> List[Tuple[str, ProviderHandler]]:
        providers: List[Tuple[str, ProviderHandler]] = []

        if getattr(mistral_service, "api_key", None):
            providers.append(("mistral", self.process_with_mistral))

        if huggingface_service.is_configured:
            providers.append(("huggingface", self._process_with_huggingface))

        if await self._is_ollama_available():
            providers.append(("ollama", self._process_with_ollama))

        return providers

    def _calculate_backoff(self, attempt: int) -> float:
        return min(2 ** (attempt - 1), 8)

    async def process_with_mistral(
        self, message: str, context: Dict[str, Any] | None = None
    ) -> str:
        """Procesar mensaje con Mistral AI."""
        if not getattr(mistral_service, "api_key", None):
            raise RuntimeError("Mistral API key no configurada")

        try:
            response = await mistral_service.generate_financial_response(message, context or {})
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Error solicitando respuesta a Mistral: {exc}") from exc

        if not response or len(response.strip()) <= 10:
            raise RuntimeError("Respuesta vacía de Mistral")

        if response.strip().lower().startswith("lo siento, estoy teniendo dificultades"):
            raise RuntimeError("Mistral no pudo generar respuesta útil")

        return response

    async def _process_with_huggingface(
        self, message: str, context: Dict[str, Any] | None = None
    ) -> str:
        try:
            return await huggingface_service.generate_financial_response(message, context or {})
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Error solicitando respuesta a HuggingFace: {exc}") from exc

    async def _process_with_ollama(
        self, message: str, context: Dict[str, Any] | None = None
    ) -> str:
        if not await self._is_ollama_available(force_refresh=False):
            raise RuntimeError("Ollama local no disponible")

        system_prompt = self._create_system_prompt(context or {})
        payload = {
            "model": self._ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            "stream": False,
        }

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._ollama_base_url}/api/chat", json=payload
                ) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        raise RuntimeError(
                            f"Ollama devolvió código {response.status}: {error_detail}"
                        )

                    data = await response.json()
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Timeout al solicitar respuesta a Ollama") from exc
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Error de conexión con Ollama: {exc}") from exc

        message_data = data.get("message") or {}
        content = message_data.get("content", "").strip()
        if not content:
            raise RuntimeError("Respuesta vacía de Ollama")

        return content

    async def _is_ollama_available(self, force_refresh: bool = False) -> bool:
        now = time.time()
        if (
            not force_refresh
            and now - self._ollama_cache["checked_at"] < self._ollama_cache_ttl
        ):
            return bool(self._ollama_cache["available"])

        timeout = aiohttp.ClientTimeout(total=5)
        available = False

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self._ollama_base_url}/api/version") as response:
                    available = response.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("No se pudo verificar Ollama: %s", exc)
            available = False

        self._ollama_cache["available"] = available
        self._ollama_cache["checked_at"] = now

        if available:
            logger.info("Ollama local detectado en %s", self._ollama_base_url)
        else:
            logger.debug("Ollama no disponible en %s", self._ollama_base_url)

        return available

    def _create_system_prompt(self, context: Dict[str, Any] | None = None) -> str:
        base_prompt = """Eres BullBearBroker, un asistente de IA especializado en mercados financieros.
Tu expertise incluye acciones, criptomonedas, forex, análisis técnico y fundamental.
Sigue siempre mejores prácticas de gestión de riesgo y comunica con tono profesional."""

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

    async def get_market_context(self, message: str) -> Dict[str, Any]:
        """Obtener contexto de mercado relevante."""
        if not self.market_service:
            return {}

        context: Dict[str, Any] = {}
        symbols = self.extract_symbols(message)

        if symbols:
            market_data: Dict[str, Any] = {}
            for symbol in symbols:
                try:
                    asset_type = await self.market_service.detect_asset_type(symbol)
                    price_data = await self.market_service.get_price(symbol, asset_type)
                    if price_data:
                        market_data[symbol] = {
                            "price": price_data.get("price", "N/A"),
                            "change": price_data.get("change", "N/A"),
                            "raw_price": price_data.get("raw_price", 0),
                            "raw_change": price_data.get("raw_change", 0),
                        }
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error obteniendo precio para %s: %s", symbol, exc)
                    continue

            if market_data:
                context["market_data"] = market_data
                context["symbols"] = list(market_data.keys())

        return context

    def extract_symbols(self, message: str) -> List[str]:
        """Extraer símbolos de activos del mensaje."""
        crypto_symbols = {
            "BTC",
            "ETH",
            "BNB",
            "XRP",
            "ADA",
            "SOL",
            "DOT",
            "AVAX",
            "MATIC",
            "DOGE",
        }

        patterns = [
            r"\b([A-Z]{2,5})\b",
            r"precio de (\w+)",
            r"valor de (\w+)",
            r"cotización de (\w+)",
            r"price of (\w+)",
            r"cuánto vale (\w+)",
        ]

        found_symbols = set()

        words = message.upper().split()
        for word in words:
            cleaned_word = word.strip('.,!?;:()[]{}')
            if cleaned_word in crypto_symbols:
                found_symbols.add(cleaned_word)
            elif len(cleaned_word) in [3, 4, 5] and cleaned_word.isalpha():
                found_symbols.add(cleaned_word)

        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    symbol = match[0].upper()
                else:
                    symbol = match.upper()

                if len(symbol) >= 2 and symbol.isalpha():
                    found_symbols.add(symbol)

        return list(found_symbols)

    async def generate_response(self, message: str) -> str:
        """Generar respuesta local (fallback)."""
        lower_message = message.lower()

        if self.is_price_query(lower_message):
            return await self.handle_price_query(message)

        responses = {
            "bitcoin": "📈 Bitcoin está mostrando fortaleza. Soporte clave en $40,000, resistencia en $45,000. Volumen aumentado 15% en 24h. Recomendación: acumular en dips.",
            "ethereum": "🔷 Ethereum consolidando en $2,500. El upgrade próximamente podría impulsar el precio. Technicals muestran patrón alcista.",
            "acciones": "💼 Recomiendo diversificar: Tech (AAPL, MSFT), Renewable Energy (ENPH), Healthcare (JNJ). Allocation sugerida: 60% stocks, 20% crypto, 20% cash.",
            "estrategia": "🎯 Estrategias: Conservadora (40% bonds, 40% blue chips, 20% gold). Agresiva (50% growth stocks, 30% crypto, 20% emerging markets). Rebalancear trimestralmente.",
            "mercado": "🌍 Mercados globales: S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo dollar-cost averaging y diversificación.",
            "forex": "💱 Forex: EUR/USD 1.0850, GBP/USD 1.2450, USD/JPY 150.20. Atención a reuniones del Fed para cambios en tasas.",
            "noticias": "📰 Sigue las noticias de: Fed meetings, earnings reports, GDP data, y regulatory announcements. Usa fuentes confiables como Bloomberg, Reuters, y Financial Times.",
            "portfolio": "📊 Para construir portfolio: 1) Define tu risk tolerance, 2) Diversifica across asset classes, 3) Considera horizonte temporal, 4) Rebalancea regularmente.",
            "riesgo": "⚖️ Gestión de riesgo: Nunca inviertas más de lo que puedes perder, diversifica, usa stop-loss orders, y mantén cash para oportunidades.",
            "inversión": "💡 Principios de inversión: Long-term perspective, dollar-cost averaging, focus on fundamentals, and avoid emotional decisions.",
        }

        for keyword, response in responses.items():
            if keyword in lower_message:
                return response

        return self.get_default_response(message)

    def is_price_query(self, message: str) -> bool:
        price_keywords = [
            "precio",
            "valor",
            "cuánto vale",
            "price of",
            "cotización",
            "valor de",
            "precio de",
            "how much is",
            "current price",
        ]
        return any(keyword in message for keyword in price_keywords)

    async def handle_price_query(self, message: str) -> str:
        if not self.market_service:
            return "Servicio de mercado no disponible en este momento."

        symbols = self.extract_symbols(message)

        if not symbols:
            return (
                "No pude identificar el símbolo del activo. Por favor especifica, por ejemplo: 'precio de BTC' o 'valor de AAPL'."
            )

        responses: List[str] = []
        for symbol in symbols[:3]:
            try:
                asset_type = await self.market_service.detect_asset_type(symbol)
                price_data = await self.market_service.get_price(symbol, asset_type)

                if price_data:
                    response = f"**{symbol}**: {price_data['price']} ({price_data['change']})"
                    responses.append(response)
                else:
                    responses.append(f"**{symbol}**: No disponible")

            except Exception as exc:  # noqa: BLE001
                logger.warning("Error obteniendo precio para %s: %s", symbol, exc)
                responses.append(f"**{symbol}**: Error obteniendo datos")

        if responses:
            return "📊 Precios actuales:\n" + "\n".join(responses)

        return "No pude obtener precios para los símbolos mencionados."

    def get_default_response(self, message: str) -> str:
        return f"""🤖 **BullBearBroker Analysis**

He analizado tu consulta sobre "{message}". Como asistente financiero especializado, te recomiendo:

📊 **Diversificación**: Spread investments across stocks, crypto, bonds, and real estate
⏰ **Horizonte Temporal**: Align investments with your time horizon and goals
📉 **Gestión de Riesgo**: Never invest more than you can afford to lose
🔍 **Due Diligence**: Research thoroughly before any investment
💡 **Educación Continua**: Stay informed about market trends and developments

**¿En qué aspecto te gustaría que profundice?**
- 📈 Análisis técnico de algún activo
- 💰 Estrategias de inversión específicas
- 📰 Impacto de noticias recientes
- 🎯 Recomendaciones de portfolio"""

    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        try:
            return await mistral_service.analyze_market_sentiment(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallo analizando sentimiento con Mistral: %s", exc)

        return {
            "sentiment_score": 0.0,
            "confidence": 0.7,
            "keywords": ["market", "analysis", "financial"],
        }


ai_service = AIService()

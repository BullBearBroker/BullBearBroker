from typing import Dict, Any, Callable, Awaitable, List, Tuple, Optional
import asyncio
import logging
import re

import aiohttp

from backend.utils.config import Config
from .mistral_service import mistral_service


logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.market_service = None
        self.use_real_ai = True  # Mantener compatibilidad con otros servicios
        
    def set_market_service(self, market_service):
        self.market_service = market_service

    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Procesar mensaje del usuario y generar respuesta"""
        context = dict(context or {})

        try:
            market_context = await self.get_market_context(message)
            context.update(market_context)
        except Exception:
            logger.exception("Error collecting market context")

        providers: List[Tuple[str, Callable[[], Awaitable[str]]]] = [
            ("mistral", lambda: self.process_with_mistral(message, context))
        ]

        if Config.HUGGINGFACE_API_TOKEN:
            providers.append(
                ("huggingface", lambda: self._call_huggingface(message, context))
            )
        else:
            logger.info("HuggingFace token not configured. Skipping provider.")

        providers.append(("ollama", lambda: self._call_ollama(message, context)))

        try:
            response, provider = await self._call_with_backoff(providers)
            logger.info("AI response generated using provider %s", provider)
            return response
        except Exception as exc:
            logger.error("Falling back to local response after provider failures: %s", exc)
            local_response = await self.generate_response(message)
            logger.info("AI response generated using local fallback")
            return local_response

    async def process_with_mistral(self, message: str, context: Dict[str, Any] = None) -> str:
        """Procesar mensaje con Mistral AI"""
        try:
            # Generar respuesta con Mistral AI
            response = await mistral_service.generate_financial_response(message, context)

            # Verificar que la respuesta sea válida
            if response and len(response.strip()) > 10:
                if "dificultades" in response.lower():
                    raise ValueError("Respuesta de error de Mistral AI")
                return response
            else:
                raise ValueError("Respuesta vacía de Mistral AI")

        except Exception as e:
            logger.warning("Mistral provider failed: %s", e)
            raise
        
    async def _call_with_backoff(
        self,
        providers: List[Tuple[str, Callable[[], Awaitable[str]]]]
    ) -> Tuple[str, str]:
        last_error: Optional[Exception] = None
        for provider_name, provider in providers:
            backoff = 1
            for attempt in range(1, 4):
                try:
                    response = await provider()
                    if response and response.strip():
                        return response, provider_name
                    raise ValueError(f"Respuesta vacía de {provider_name}")
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Provider %s attempt %d failed: %s",
                        provider_name,
                        attempt,
                        exc
                    )
                    if attempt < 3:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.error(
                            "Provider %s exhausted retries after %d attempts",
                            provider_name,
                            attempt
                        )
                        break

        if last_error:
            raise last_error
        raise RuntimeError("No providers available")

    async def _call_huggingface(self, message: str, context: Dict[str, Any]) -> str:
        if not Config.HUGGINGFACE_API_TOKEN:
            raise RuntimeError("HuggingFace token not configured")

        model = Config.HUGGINGFACE_MODEL
        base_url = Config.HUGGINGFACE_API_URL.rstrip('/')
        url = f"{base_url}/{model}"
        prompt = self._build_prompt(message, context)

        headers = {
            "Authorization": f"Bearer {Config.HUGGINGFACE_API_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 400,
                "temperature": 0.4
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                if response.status != 200:
                    error_body = await response.text()
                    raise RuntimeError(
                        f"HuggingFace API error {response.status}: {error_body}"
                    )

                data = await response.json()

        generated_text: str | None = None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("generated_text"), str):
                    generated_text = item["generated_text"]
                    break
                if isinstance(item, str):
                    generated_text = item
                    break
        elif isinstance(data, dict):
            text_candidate = data.get("generated_text") or data.get("data")
            if isinstance(text_candidate, str):
                generated_text = text_candidate

        if generated_text and generated_text.strip():
            return generated_text.strip()

        raise ValueError("Respuesta vacía de HuggingFace")

    async def _call_ollama(self, message: str, context: Dict[str, Any]) -> str:
        host = Config.OLLAMA_HOST.rstrip('/') if Config.OLLAMA_HOST else "http://localhost:11434"
        model = Config.OLLAMA_MODEL or "llama3"
        prompt = self._build_prompt(message, context)

        async with aiohttp.ClientSession() as session:
            # Verificar que el servidor de Ollama esté disponible y que el modelo exista
            async with session.get(f"{host}/api/tags", timeout=5) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(f"Ollama disponibilidad fallida: {body}")

                tags = await response.json()
                models = tags.get("models") if isinstance(tags, dict) else None
                if isinstance(models, list):
                    if not any(isinstance(item, dict) and item.get("name") == model for item in models):
                        raise RuntimeError(f"Modelo {model} no disponible en Ollama")

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }

            async with session.post(f"{host}/api/generate", json=payload, timeout=30) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(f"Error generando respuesta de Ollama: {body}")

                data = await response.json()

        generated_text = data.get("response") if isinstance(data, dict) else None
        if isinstance(generated_text, str) and generated_text.strip():
            return generated_text.strip()

        raise ValueError("Respuesta vacía de Ollama")

    def _build_prompt(self, message: str, context: Dict[str, Any]) -> str:
        prompt_lines = [
            "Eres BullBearBroker, un analista financiero profesional.",
            f"Consulta del usuario: {message}"
        ]

        if context:
            market_data = context.get("market_data")
            if market_data:
                prompt_lines.append(f"Datos de mercado: {market_data}")

            other_context = {
                key: value for key, value in context.items()
                if key not in {"market_data"}
            }
            if other_context:
                prompt_lines.append(f"Contexto adicional: {other_context}")

        prompt_lines.append("Responde en español con recomendaciones concretas y breves.")
        return "\n".join(prompt_lines)

    async def get_market_context(self, message: str) -> Dict[str, Any]:
        """Obtener contexto de mercado relevante"""
        if not self.market_service:
            return {}

        context = {}
        symbols = self.extract_symbols(message)
        
        if symbols:
            market_data = {}
            for symbol in symbols:
                try:
                    asset_type = await self.market_service.detect_asset_type(symbol)
                    price_data = await self.market_service.get_price(symbol, asset_type)
                    if price_data:
                        market_data[symbol] = {
                            'price': price_data.get('price', 'N/A'),
                            'change': price_data.get('change', 'N/A'),
                            'raw_price': price_data.get('raw_price', 0),
                            'raw_change': price_data.get('raw_change', 0)
                        }
                except Exception as e:
                    print(f"Error getting price for {symbol}: {e}")
                    continue
            
            if market_data:
                context['market_data'] = market_data
                context['symbols'] = list(market_data.keys())

        return context

    def extract_symbols(self, message: str) -> list:
        """Extraer símbolos de activos del mensaje"""
        # Símbolos de cripto comunes
        crypto_symbols = {'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'AVAX', 'MATIC', 'DOGE'}
        
        # Patrones regex para detectar símbolos
        patterns = [
            r'\b([A-Z]{2,5})\b',  # Símbolos de acciones (AAPL, TSLA)
            r'precio de (\w+)',
            r'valor de (\w+)', 
            r'cotización de (\w+)',
            r'price of (\w+)',
            r'cuánto vale (\w+)'
        ]
        
        found_symbols = set()
        
        # Buscar símbolos conocidos
        words = message.upper().split()
        for word in words:
            cleaned_word = word.strip('.,!?;:()[]{}')
            if cleaned_word in crypto_symbols:
                found_symbols.add(cleaned_word)
            elif len(cleaned_word) in [3, 4, 5] and cleaned_word.isalpha():
                found_symbols.add(cleaned_word)
        
        # Buscar con patrones regex
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
        """Generar respuesta local (fallback)"""
        lower_message = message.lower()
        
        # Detectar consultas de precio
        if self.is_price_query(lower_message):
            return await self.handle_price_query(message)
        
        # Respuestas predefinidas
        responses = {
            'bitcoin': '📈 Bitcoin está mostrando fortaleza. Soporte clave en $40,000, resistencia en $45,000. Volumen aumentado 15% en 24h. Recomendación: acumular en dips.',
            'ethereum': '🔷 Ethereum consolidando en $2,500. El upgrade próximamente podría impulsar el precio. Technicals muestran patrón alcista.',
            'acciones': '💼 Recomiendo diversificar: Tech (AAPL, MSFT), Renewable Energy (ENPH), Healthcare (JNJ). Allocation sugerida: 60% stocks, 20% crypto, 20% cash.',
            'estrategia': '🎯 Estrategias: Conservadora (40% bonds, 40% blue chips, 20% gold). Agresiva (50% growth stocks, 30% crypto, 20% emerging markets). Rebalancear trimestralmente.',
            'mercado': '🌍 Mercados globales: S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo dollar-cost averaging y diversificación.',
            'forex': '💱 Forex: EUR/USD 1.0850, GBP/USD 1.2450, USD/JPY 150.20. Atención a reuniones del Fed para cambios en tasas.',
            'noticias': '📰 Sigue las noticias de: Fed meetings, earnings reports, GDP data, y regulatory announcements. Usa fuentes confiables como Bloomberg, Reuters, y Financial Times.',
            'portfolio': '📊 Para construir portfolio: 1) Define tu risk tolerance, 2) Diversifica across asset classes, 3) Considera horizonte temporal, 4) Rebalancea regularmente.',
            'riesgo': '⚖️ Gestión de riesgo: Nunca inviertas más de lo que puedes perder, diversifica, usa stop-loss orders, y mantén cash para oportunidades.',
            'inversión': '💡 Principios de inversión: Long-term perspective, dollar-cost averaging, focus on fundamentals, and avoid emotional decisions.'
        }
        
        for keyword, response in responses.items():
            if keyword in lower_message:
                return response
        
        # Respuesta por defecto para consultas generales
        return self.get_default_response(message)

    def is_price_query(self, message: str) -> bool:
        """Detectar si es una consulta de precio"""
        price_keywords = [
            'precio', 'valor', 'cuánto vale', 'price of', 'cotización',
            'valor de', 'precio de', 'how much is', 'current price'
        ]
        return any(keyword in message for keyword in price_keywords)

    async def handle_price_query(self, message: str) -> str:
        """Manejar consultas de precio"""
        if not self.market_service:
            return "Servicio de mercado no disponible en este momento."
        
        symbols = self.extract_symbols(message)
        
        if not symbols:
            return "No pude identificar el símbolo del activo. Por favor especifica, por ejemplo: 'precio de BTC' o 'valor de AAPL'."
        
        responses = []
        for symbol in symbols[:3]:  # Limitar a 3 símbolos por respuesta
            try:
                asset_type = await self.market_service.detect_asset_type(symbol)
                price_data = await self.market_service.get_price(symbol, asset_type)
                
                if price_data:
                    response = f"**{symbol}**: {price_data['price']} ({price_data['change']})"
                    responses.append(response)
                else:
                    responses.append(f"**{symbol}**: No disponible")
                    
            except Exception as e:
                print(f"Error getting price for {symbol}: {e}")
                responses.append(f"**{symbol}**: Error obteniendo datos")
        
        if responses:
            return "📊 Precios actuales:\n" + "\n".join(responses)
        else:
            return "No pude obtener precios para los símbolos mencionados."

    def get_default_response(self, message: str) -> str:
        """Respuesta por defecto para consultas generales"""
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

    async def get_fallback_response(self, message: str) -> str:
        """Respuesta de fallback para errores"""
        return f"""⚠️ **Estoy teniendo dificultades técnicas**

Lo siento, estoy experimentando problemas temporales para procesar tu solicitud sobre "{message}".

Mientras tanto, te sugiero:
1. 📊 Verificar precios directamente en exchanges confiables
2. 📰 Consultar noticias financieras recientes
3. 🔍 Realizar tu propio análisis fundamental

**Por favor intenta nuevamente en unos minutos.** Estoy trabajando para resolver el issue.

¿Hay algo más en lo que pueda ayudarte?"""

    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analizar sentimiento de texto (para noticias)"""
        try:
            if self.use_real_ai:
                return await mistral_service.analyze_market_sentiment(text)
        except:
            pass
        
        # Fallback simple
        return {
            "sentiment_score": 0.0,
            "confidence": 0.7,
            "keywords": ["market", "analysis", "financial"]
        }

# Singleton instance
ai_service = AIService()

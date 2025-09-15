from typing import Dict, Any
import asyncio
import re
from .mistral_service import mistral_service

class AIService:
    def __init__(self):
        self.market_service = None
        self.use_real_ai = True  # Cambiar a False si falla Mistral
        
    def set_market_service(self, market_service):
        self.market_service = market_service

    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Procesar mensaje del usuario y generar respuesta"""
        try:
            if self.use_real_ai:
                # 🚀 USAR MISTRAL AI REAL
                return await self.process_with_mistral(message, context)
            else:
                # 🆘 FALLBACK a respuestas locales
                return await self.generate_response(message)
                
        except Exception as e:
            print(f"Error processing message: {e}")
            return await self.get_fallback_response(message)

    async def process_with_mistral(self, message: str, context: Dict[str, Any] = None) -> str:
        """Procesar mensaje con Mistral AI"""
        try:
            # Obtener contexto de mercado si está disponible
            market_context = await self.get_market_context(message)
            if context is None:
                context = {}
            context.update(market_context)

            # Generar respuesta con Mistral AI
            response = await mistral_service.generate_financial_response(message, context)
            
            # Verificar que la respuesta sea válida
            if response and len(response.strip()) > 10:
                return response
            else:
                raise ValueError("Respuesta vacía de Mistral AI")
                
        except Exception as e:
            print(f"Mistral AI failed, using fallback: {e}")
            self.use_real_ai = False  # Temporalmente desactivar IA real
            return await self.generate_response(message)

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
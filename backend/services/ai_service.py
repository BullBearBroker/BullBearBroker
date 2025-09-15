from typing import Dict, Any
import asyncio

class AIService:
    def __init__(self):
        self.market_service = None
        
    def set_market_service(self, market_service):
        self.market_service = market_service

    async def process_message(self, message: str) -> str:
        """Procesar mensaje del usuario y generar respuesta"""
        try:
            # Simular procesamiento con IA
            # Luego integraremos Mistral/Claude API
            return await self.generate_response(message)
        except Exception as e:
            print(f"Error processing message: {e}")
            return "Lo siento, estoy teniendo dificultades para procesar tu solicitud. Por favor intenta nuevamente."

    async def generate_response(self, message: str) -> str:
        """Generar respuesta basada en el mensaje"""
        lower_message = message.lower()
        
        # Detectar consultas de precio
        price_keywords = ['precio', 'valor', 'cuánto vale', 'price of', 'cotización']
        if any(keyword in lower_message for keyword in price_keywords):
            return await self.handle_price_query(message)
        
        # Respuestas predefinidas
        responses = {
            'bitcoin': '📈 Bitcoin está mostrando fortaleza. Soporte clave en $40,000, resistencia en $45,000. Volumen aumentado 15% en 24h.',
            'ethereum': '🔷 Ethereum consolidando alrededor de $2,500. El upgrade próximamente podría impulsar el precio significativamente.',
            'acciones': '💼 Recomiendo diversificar: Tecnología (AAPL, MSFT), Energía Renovable (ENPH), Healthcare (JNJ).',
            'estrategia': '🎯 Para perfiles conservadores: 40% bonds, 40% blue chips, 20% gold. Agresivos: 50% growth stocks, 30% crypto, 20% emerging markets.',
            'mercado': '🌍 Mercados globales: S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo cautela y diversificación.',
            'forex': '💱 Principales pares: EUR/USD 1.0850, GBP/USD 1.2450, USD/JPY 150.20. Atención a reuniones del Fed.'
        }
        
        for keyword, response in responses.items():
            if keyword in lower_message:
                return response
        
        # Respuesta por defecto
        return f"""He analizado tu consulta sobre "{message}". Como asistente financiero, te recomiendo:

1. 📊 Diversificar entre diferentes clases de activos
2. ⏰ Considerar tu horizonte temporal de inversión
3. 📉 Mantener algo de cash para oportunidades de mercado
4. 🔍 Realizar due diligence antes de cada inversión

¿Te gustaría que profundice en algún aspecto en particular?"""

    async def handle_price_query(self, message: str) -> str:
        """Manejar consultas de precio"""
        if not self.market_service:
            return "Servicio de mercado no disponible en este momento."
        
        # Extraer símbolo del mensaje
        symbols = ['BTC', 'ETH', 'AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        found_symbol = None
        
        for symbol in symbols:
            if symbol.lower() in message.lower():
                found_symbol = symbol
                break
        
        if not found_symbol:
            # Intentar extraer cualquier palabra en mayúsculas
            words = message.split()
            for word in words:
                if word.isupper() and len(word) <= 5:
                    found_symbol = word
                    break
        
        if found_symbol:
            price_data = await self.market_service.get_price(found_symbol)
            if price_data:
                return f"El precio actual de {found_symbol} es {price_data['price']} ({price_data['change']} en 24h)."
            else:
                return f"No tengo información del precio de {found_symbol} en este momento."
        
        return "No pude identificar el símbolo del activo. Por favor especifica, por ejemplo: 'precio de BTC' o 'valor de AAPL'."

# Singleton instance
ai_service = AIService()
import aiohttp
import json
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class MistralService:
    def __init__(self):
        self.api_key = os.getenv('MISTRAL_API_KEY')
        self.base_url = "https://api.mistral.ai/v1"
        self.models = {
            'small': 'mistral-small-latest',
            'medium': 'mistral-medium-latest', 
            'large': 'mistral-large-latest'
        }
    
    async def chat_completion(self, messages: list, model: str = 'medium') -> Optional[str]:
        """
        Enviar mensajes a Mistral AI y obtener respuesta
        """
        if not self.api_key:
            raise ValueError("Mistral API key no configurada")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.models[model],
            'messages': messages,
            'temperature': 0.1,  # Baja temperatura para respuestas precisas
            'max_tokens': 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_data = await response.text()
                        print(f"Mistral API error: {response.status} - {error_data}")
                        return None
                        
        except Exception as e:
            print(f"Error calling Mistral AI: {e}")
            return None
    
    async def generate_financial_response(self, user_message: str, context: Dict[str, Any] = None) -> str:
        """
        Generar respuesta especializada en finanzas
        """
        # Preparar el contexto del sistema
        system_prompt = self._create_system_prompt(context)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = await self.chat_completion(messages, model='medium')
        
        if not response:
            return "Lo siento, estoy teniendo dificultades para procesar tu solicitud. Por favor intenta nuevamente."
        
        return response
    
    def _create_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """
        Crear prompt del sistema especializado en finanzas
        """
        base_prompt = """Eres BullBearBroker, un asistente de IA especializado en mercados financieros. 
        Tu expertise incluye: acciones, criptomonedas, forex, análisis técnico y fundamental.

        Reglas importantes:
        1. Sé preciso y basado en datos reales
        2. Proporciona análisis objetivos sin bias emocional
        3. Incluye datos concretos cuando sea posible
        4. Advierte sobre riesgos cuando sea apropiado
        5. Mantén un tono profesional pero accesible

        Formato de respuestas:
        - Incluye emojis relevantes (📈, ₿, 🔍)
        - Usa negritas para puntos importantes
        - Proporciona insights accionables
        - Sé conciso pero completo"""

        if context:
            # Agregar contexto específico si está disponible
            context_str = "\nContexto adicional:\n"
            if 'market_data' in context:
                context_str += f"Datos de mercado: {context['market_data']}\n"
            if 'user_portfolio' in context:
                context_str += f"Portfolio usuario: {context['user_portfolio']}\n"
            
            return base_prompt + context_str
        
        return base_prompt
    
    async def analyze_market_sentiment(self, news_text: str) -> Dict[str, float]:
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
            {"role": "system", "content": "Eres un analista de sentimiento financiero. Devuelve SOLO JSON válido."},
            {"role": "user", "content": prompt}
        ]

        response = await self.chat_completion(messages, model='small')
        
        try:
            if response:
                return json.loads(response.strip())
        except:
            pass
        
        return {"sentiment_score": 0.0, "confidence": 0.0, "keywords": []}

# Singleton instance
mistral_service = MistralService()
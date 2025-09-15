import aiohttp
import asyncio
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class MarketService:
    def __init__(self):
        self.api_keys = {
            'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', 'demo'),
            'coin_gecko': os.getenv('COIN_GECKO_API_KEY', '')
        }
        self.base_urls = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'coin_gecko': 'https://api.coingecko.com/api/v3'
        }

    async def get_top_performers(self) -> Dict:
        """Obtener los mejores performers del mercado"""
        try:
            # Simular datos por ahora - luego integraremos APIs reales
            return await self.get_simulated_data()
        except Exception as e:
            print(f"Error getting market data: {e}")
            return await self.get_simulated_data()

    async def get_price(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de un activo específico"""
        try:
            # Primero intentar con cripto
            if symbol.upper() in ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL']:
                price_data = await self.get_crypto_price(symbol)
                if price_data:
                    return price_data
            
            # Luego intentar con acciones
            price_data = await self.get_stock_price(symbol)
            if price_data:
                return price_data
                
            return None
                
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None

    async def get_crypto_price(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de criptomoneda"""
        try:
            # Simulado por ahora - integrar CoinGecko API luego
            crypto_prices = {
                'BTC': {'price': 45123.45, 'change': 2.5},
                'ETH': {'price': 2567.89, 'change': 1.8},
                'BNB': {'price': 312.45, 'change': 0.2},
                'XRP': {'price': 0.58, 'change': -0.3},
                'ADA': {'price': 0.45, 'change': -0.1},
                'DOGE': {'price': 0.12, 'change': -0.2},
                'SOL': {'price': 95.67, 'change': 1.2}
            }
            
            if symbol.upper() in crypto_prices:
                data = crypto_prices[symbol.upper()]
                return {
                    'price': f"${data['price']:,.2f}",
                    'change': f"{'+' if data['change'] >= 0 else ''}{data['change']}%",
                    'raw_price': data['price'],
                    'raw_change': data['change']
                }
            return None
            
        except Exception as e:
            print(f"Error getting crypto price: {e}")
            return None

    async def get_stock_price(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de accion"""
        try:
            # Simulado por ahora - integrar Alpha Vantage luego
            stock_prices = {
                'AAPL': {'price': 178.90, 'change': 0.7},
                'TSLA': {'price': 245.67, 'change': -0.8},
                'MSFT': {'price': 345.21, 'change': 0.3},
                'GOOGL': {'price': 145.32, 'change': 0.5},
                'AMZN': {'price': 178.56, 'change': 0.4},
                'NVDA': {'price': 456.78, 'change': 1.5},
                'META': {'price': 467.89, 'change': 0.9}
            }
            
            if symbol.upper() in stock_prices:
                data = stock_prices[symbol.upper()]
                return {
                    'price': f"${data['price']:.2f}",
                    'change': f"{'+' if data['change'] >= 0 else ''}{data['change']}%",
                    'raw_price': data['price'],
                    'raw_change': data['change']
                }
            return None
            
        except Exception as e:
            print(f"Error getting stock price: {e}")
            return None

    async def get_simulated_data(self) -> Dict:
        """Datos simulados para desarrollo"""
        return {
            'top_performers': [
                {'symbol': 'BTC', 'price': '$45,123.45', 'change': '+2.5%', 'type': 'crypto'},
                {'symbol': 'ETH', 'price': '$2,567.89', 'change': '+1.8%', 'type': 'crypto'},
                {'symbol': 'AAPL', 'price': '$178.90', 'change': '+0.7%', 'type': 'stock'},
                {'symbol': 'MSFT', 'price': '$345.21', 'change': '+0.3%', 'type': 'stock'},
                {'symbol': 'SOL', 'price': '$95.67', 'change': '+1.2%', 'type': 'crypto'}
            ],
            'worst_performers': [
                {'symbol': 'TSLA', 'price': '$245.67', 'change': '-0.8%', 'type': 'stock'},
                {'symbol': 'XRP', 'price': '$0.58', 'change': '-0.3%', 'type': 'crypto'},
                {'symbol': 'NFLX', 'price': '$567.89', 'change': '-0.5%', 'type': 'stock'},
                {'symbol': 'DOGE', 'price': '$0.12', 'change': '-0.2%', 'type': 'crypto'},
                {'symbol': 'ADA', 'price': '$0.45', 'change': '-0.1%', 'type': 'crypto'}
            ],
            'market_summary': {
                'sp500': '+0.3%',
                'nasdaq': '+0.8%', 
                'dow_jones': '-0.2%',
                'bitcoin_dominance': '52.3%'
            }
        }

    async def close(self):
        """Cerrar conexiones"""
        pass

# Singleton instance
market_service = MarketService()
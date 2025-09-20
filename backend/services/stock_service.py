import aiohttp
import asyncio
from typing import List, Dict, Optional
from utils.config import Config

class StockService:
    def __init__(self):
        self.apis = {
            'primary': self.alpha_vantage,
            'secondary': self.twelvedata, 
            'fallback': self.yahoo_finance
        }
    
    async def get_price(self, symbol: str) -> Optional[float]:
        """Obtener precio de stock de 3 fuentes en paralelo"""
        try:
            results = await asyncio.gather(
                self.apis['primary'](symbol),
                self.apis['secondary'](symbol),
                self.apis['fallback'](symbol),
                return_exceptions=True
            )
            
            valid_prices = self._process_results(results)
            return self._calculate_final_price(valid_prices)
            
        except Exception as e:
            print(f"Error getting stock price: {e}")
            return None
    
    async def alpha_vantage(self, symbol: str) -> float:
        """API Primaria: Alpha Vantage"""
        url = f"https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': Config.ALPHA_VANTAGE_API_KEY
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return float(data['Global Quote']['05. price'])
    
    async def twelvedata(self, symbol: str) -> float:
        """API Secundaria: Twelve Data"""
        url = f"https://api.twelvedata.com/price"
        params = {
            'symbol': symbol,
            'apikey': Config.TWELVEDATA_API_KEY
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return float(data['price'])
    
    async def yahoo_finance(self, symbol: str) -> float:
        """API Fallback: Yahoo Finance (no necesita key)"""
        # Implementación simple - luego podemos mejorar
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return data['chart']['result'][0]['meta']['regularMarketPrice']
    
    def _process_results(self, results: List) -> List[float]:
        """Filtrar resultados válidos"""
        valid_prices = []
        for result in results:
            if not isinstance(result, Exception):
                if isinstance(result, (int, float)) and result > 0:
                    valid_prices.append(result)
        return valid_prices
    
    def _calculate_final_price(self, prices: List[float]) -> float:
        """Calcular precio final (mediana para evitar outliers)"""
        if not prices:
            raise ValueError("No valid prices received")
        
        sorted_prices = sorted(prices)
        return sorted_prices[len(sorted_prices) // 2]

import aiohttp
import asyncio
import logging
from typing import List, Optional
from utils.config import Config

class CryptoService:
    def __init__(self):
        self.apis = {
            'primary': self.coingecko,
            'secondary': self.binance,
            'fallback': self.coinmarketcap
        }
        self.logger = logging.getLogger(__name__)
    
    async def get_price(self, symbol: str) -> Optional[float]:
        """Obtener precio crypto de 3 fuentes en paralelo"""
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
            self.logger.exception("Error getting crypto price: %s", e)
            return None
    
    async def coingecko(self, symbol: str) -> float:
        """API Primaria: CoinGecko"""
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': symbol.lower(),
            'vs_currencies': 'usd'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return data[symbol.lower()]['usd']
    
    async def binance(self, symbol: str) -> float:
        """API Secundaria: Binance"""
        url = f"https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': f"{symbol}USDT"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return float(data['price'])
    
    async def coinmarketcap(self, symbol: str) -> float:
        """API Fallback: CoinMarketCap"""
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {'X-CMC_PRO_API_KEY': Config.COINMARKETCAP_API_KEY}
        params = {'symbol': symbol}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
                return data['data'][symbol]['quote']['USD']['price']
    
    def _process_results(self, results: List) -> List[float]:
        """Filtrar resultados válidos"""
        valid_prices = []
        for result in results:
            if not isinstance(result, Exception):
                if isinstance(result, (int, float)) and result > 0:
                    valid_prices.append(result)
        return valid_prices
    
    def _calculate_final_price(self, prices: List[float]) -> float:
        """Calcular precio final"""
        if not prices:
            raise ValueError("No valid prices received")
        
        sorted_prices = sorted(prices)
        return sorted_prices[len(sorted_prices) // 2]

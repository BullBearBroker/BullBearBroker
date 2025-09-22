import aiohttp
import asyncio
from typing import Dict, List, Optional

from utils.cache import CacheClient
from utils.config import Config

class CryptoService:
    def __init__(self, cache_client: Optional[CacheClient] = None):
        self.apis = {
            'primary': self.coingecko,
            'secondary': self.binance,
            'fallback': self.coinmarketcap
        }
        self.cache = cache_client or CacheClient('crypto-prices', ttl=45)
        self._coingecko_id_cache: Dict[str, Optional[str]] = {}

    async def get_price(self, symbol: str) -> Optional[float]:
        """Obtener precio crypto de 3 fuentes en paralelo"""
        try:
            cached_value = await self.cache.get(symbol.upper())
            if cached_value is not None:
                return cached_value

            results = await asyncio.gather(
                self.apis['primary'](symbol),
                self.apis['secondary'](symbol),
                self.apis['fallback'](symbol),
                return_exceptions=True
            )

            valid_prices = self._process_results(results)
            final_price = self._calculate_final_price(valid_prices)
            await self.cache.set(symbol.upper(), final_price)
            return final_price

        except Exception as e:
            print(f"Error getting crypto price: {e}")
            return None
    
    async def coingecko(self, symbol: str) -> Optional[float]:
        """API Primaria: CoinGecko"""
        try:
            coin_id = await self._resolve_coingecko_id(symbol)
        except Exception:
            return None

        if not coin_id:
            return None

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd'
        }

        try:
            data = await self._request_json(url, params=params)
        except Exception:
            return None

        price = data.get(coin_id, {}).get('usd')
        if isinstance(price, (int, float)):
            return float(price)
        return None
    
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

    async def _request_json(self, url: str, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

    async def _resolve_coingecko_id(self, symbol: str) -> Optional[str]:
        normalized = symbol.lower()
        if normalized in self._coingecko_id_cache:
            return self._coingecko_id_cache[normalized]

        url = "https://api.coingecko.com/api/v3/search"
        params = {'query': symbol}

        try:
            data = await self._request_json(url, params=params)
        except Exception:
            self._coingecko_id_cache[normalized] = None
            return None

        for coin in data.get('coins', []):
            if coin.get('symbol', '').lower() == normalized:
                coin_id = coin.get('id')
                self._coingecko_id_cache[normalized] = coin_id
                return coin_id

        self._coingecko_id_cache[normalized] = None
        return None
    
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

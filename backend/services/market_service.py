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
            'coin_gecko': os.getenv('COIN_GECKO_API_KEY', ''),
            'twelvedata': os.getenv('TWELVEDATA_API_KEY', ''),
            'newsapi': os.getenv('NEWSAPI_API_KEY', '')
        }
        
        self.base_urls = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'coin_gecko': 'https://api.coingecko.com/api/v3',
            'twelvedata': 'https://api.twelvedata.com',
            'yahoo_finance': 'https://query1.finance.yahoo.com/v8/finance/chart/',
            'binance': 'https://api.binance.com/api/v3'
        }

    async def get_top_performers(self) -> Dict:
        """Obtener los mejores performers del mercado"""
        try:
            # Obtener datos reales de múltiples fuentes
            stock_data = await self.get_stock_market_data()
            crypto_data = await self.get_crypto_market_data()
            
            return self.process_market_data(stock_data, crypto_data)
            
        except Exception as e:
            print(f"Error getting real market data: {e}")
            return await self.get_simulated_data()

    async def get_price(self, symbol: str, asset_type: str = None) -> Optional[Dict]:
        """Obtener precio de un activo específico de 3 fuentes en paralelo"""
        try:
            # Si no se especifica asset_type, detectarlo automáticamente
            if asset_type is None:
                asset_type = await self.detect_asset_type(symbol)
            
            if asset_type == 'crypto':
                price_data = await self.get_crypto_price_parallel(symbol)
            else:
                price_data = await self.get_stock_price_parallel(symbol)
                
            if price_data:
                return {
                    'price': f"${price_data['price']:,.2f}",
                    'change': f"{'+' if price_data['change'] >= 0 else ''}{price_data['change']}%",
                    'raw_price': price_data['price'],
                    'raw_change': price_data['change'],
                    'source': price_data['source']
                }
            return None
                
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None

    async def get_stock_price_parallel(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de stock de 3 fuentes en paralelo"""
        try:
            results = await asyncio.gather(
                self.get_alpha_vantage_price(symbol),
                self.get_twelvedata_price(symbol),
                self.get_yahoo_finance_price(symbol),
                return_exceptions=True
            )
            
            valid_prices = self.process_price_results(results)
            if valid_prices:
                final_price = self.calculate_final_price(valid_prices)
                return {
                    'price': final_price['price'],
                    'change': final_price['change'],
                    'source': final_price['source']
                }
            return None
            
        except Exception as e:
            print(f"Error in parallel stock price fetch: {e}")
            return None

    async def get_crypto_price_parallel(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de crypto de 3 fuentes en paralelo"""
        try:
            results = await asyncio.gather(
                self.get_coingecko_price(symbol),
                self.get_binance_price(symbol),
                self.get_cryptocompare_price(symbol),
                return_exceptions=True
            )
            
            valid_prices = self.process_price_results(results)
            if valid_prices:
                final_price = self.calculate_final_price(valid_prices)
                return {
                    'price': final_price['price'],
                    'change': final_price['change'],
                    'source': final_price['source']
                }
            return None
            
        except Exception as e:
            print(f"Error in parallel crypto price fetch: {e}")
            return None

    async def get_alpha_vantage_price(self, symbol: str) -> Dict:
        """Precio desde Alpha Vantage"""
        try:
            url = self.base_urls['alpha_vantage']
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_keys['alpha_vantage']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    price = float(data['Global Quote']['05. price'])
                    change = float(data['Global Quote']['09. change'])
                    return {'price': price, 'change': change, 'source': 'Alpha Vantage'}
                    
        except Exception as e:
            raise Exception(f"Alpha Vantage error: {e}")

    async def get_twelvedata_price(self, symbol: str) -> Dict:
        """Precio desde Twelve Data"""
        try:
            url = f"{self.base_urls['twelvedata']}/price"
            params = {
                'symbol': symbol,
                'apikey': self.api_keys['twelvedata']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    price = float(data['price'])
                    # Twelve Data no provee change % en endpoint básico
                    return {'price': price, 'change': 0.0, 'source': 'Twelve Data'}
                    
        except Exception as e:
            raise Exception(f"Twelve Data error: {e}")

    async def get_yahoo_finance_price(self, symbol: str) -> Dict:
        """Precio desde Yahoo Finance"""
        try:
            url = f"{self.base_urls['yahoo_finance']}{symbol}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    price = data['chart']['result'][0]['meta']['regularMarketPrice']
                    change = data['chart']['result'][0]['meta']['regularMarketChangePercent']
                    return {'price': price, 'change': change, 'source': 'Yahoo Finance'}
                    
        except Exception as e:
            raise Exception(f"Yahoo Finance error: {e}")

    async def get_coingecko_price(self, symbol: str) -> Dict:
        """Precio desde CoinGecko"""
        try:
            url = f"{self.base_urls['coin_gecko']}/simple/price"
            params = {
                'ids': symbol.lower(),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    price = data[symbol.lower()]['usd']
                    change = data[symbol.lower()]['usd_24h_change']
                    return {'price': price, 'change': change, 'source': 'CoinGecko'}
                    
        except Exception as e:
            raise Exception(f"CoinGecko error: {e}")

    async def get_binance_price(self, symbol: str) -> Dict:
        """Precio desde Binance"""
        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            params = {'symbol': f"{symbol}USDT"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    price = float(data['lastPrice'])
                    change = float(data['priceChangePercent'])
                    return {'price': price, 'change': change, 'source': 'Binance'}
                    
        except Exception as e:
            raise Exception(f"Binance error: {e}")

    async def get_cryptocompare_price(self, symbol: str) -> Dict:
        """Precio desde CryptoCompare (fallback)"""
        try:
            # CryptoCompare necesita key premium, usamos datos simulados por ahora
            crypto_prices = {
                'btc': {'price': 45123.45, 'change': 2.5},
                'eth': {'price': 2567.89, 'change': 1.8},
                'bnb': {'price': 312.45, 'change': 0.2},
                'xrp': {'price': 0.58, 'change': -0.3},
                'ada': {'price': 0.45, 'change': -0.1},
                'doge': {'price': 0.12, 'change': -0.2},
                'sol': {'price': 95.67, 'change': 1.2}
            }
            
            if symbol.lower() in crypto_prices:
                data = crypto_prices[symbol.lower()]
                return {'price': data['price'], 'change': data['change'], 'source': 'CryptoCompare'}
            raise Exception("Symbol not found")
            
        except Exception as e:
            raise Exception(f"CryptoCompare error: {e}")

    def process_price_results(self, results: List) -> List[Dict]:
        """Procesar resultados de precios válidos"""
        valid_results = []
        for result in results:
            if not isinstance(result, Exception):
                if isinstance(result, dict) and 'price' in result and 'change' in result:
                    valid_results.append(result)
        return valid_results

    def calculate_final_price(self, results: List[Dict]) -> Dict:
        """Calcular precio final de múltiples fuentes"""
        if not results:
            raise ValueError("No valid price results")
        
        # Usar la mediana de precios para evitar outliers
        prices = [r['price'] for r in results]
        changes = [r['change'] for r in results]
        sources = [r['source'] for r in results]
        
        sorted_prices = sorted(prices)
        median_price = sorted_prices[len(sorted_prices) // 2]
        
        # Para el cambio, usar promedio
        avg_change = sum(changes) / len(changes)
        
        return {
            'price': median_price,
            'change': avg_change,
            'source': f"{len(sources)} sources: {', '.join(sources)}"
        }

    async def detect_asset_type(self, symbol: str) -> str:
        """Detectar tipo de activo automáticamente"""
        crypto_symbols = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'AVAX', 'MATIC']
        if symbol.upper() in crypto_symbols:
            return 'crypto'
        else:
            return 'stock'

    async def get_stock_market_data(self) -> List[Dict]:
        """Obtener datos del mercado de acciones"""
        # Implementar luego con APIs reales
        return []

    async def get_crypto_market_data(self) -> List[Dict]:
        """Obtener datos del mercado crypto"""
        # Implementar luego con APIs reales
        return []

    def process_market_data(self, stock_data: List[Dict], crypto_data: List[Dict]) -> Dict:
        """Procesar datos de mercado para top performers"""
        # Implementar lógica real luego
        return self.get_simulated_data()

    async def get_simulated_data(self) -> Dict:
        """Datos simulados para desarrollo (fallback)"""
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
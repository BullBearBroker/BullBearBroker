import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
import os
from dotenv import load_dotenv
import json
import time

load_dotenv()

class MarketService:
    def __init__(self):
        self.api_keys = {
            'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', 'demo'),
            'coin_gecko': os.getenv('COIN_GECKO_API_KEY', ''),
            'twelvedata': os.getenv('TWELVEDATA_API_KEY', ''),
            'newsapi': os.getenv('NEWSAPI_API_KEY', ''),
            'binance': os.getenv('BINANCE_API_KEY', ''),
            'binance_secret': os.getenv('BINANCE_API_SECRET', '')
        }
        
        self.base_urls = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'coin_gecko': 'https://api.coingecko.com/api/v3',
            'twelvedata': 'https://api.twelvedata.com',
            'yahoo_finance': 'https://query1.finance.yahoo.com/v8/finance/chart/',
            'binance': 'https://api.binance.com/api/v3',
            'binance_futures': 'https://fapi.binance.com/fapi/v1'
        }
        
        # Cache para datos de Binance
        self.binance_cache = {}
        self.cache_timeout = 2  # segundos (más rápido para datos en tiempo real)

    async def get_top_performers(self) -> Dict:
        """Obtener los mejores performers del mercado con datos reales de Binance"""
        try:
            # Obtener datos reales de Binance para cripto
            crypto_data = await self.get_binance_top_performers()
            # Obtener datos de acciones
            stock_data = await self.get_stock_market_data()
            
            return await self.process_market_data(stock_data, crypto_data)
            
        except Exception as e:
            print(f"Error getting real market data: {e}")
            return await self.get_simulated_data()

    async def get_binance_top_performers(self) -> Dict:
        """Obtener top performers de Binance"""
        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Filtrar solo USDT pairs y ordenar por cambio porcentual
                        usdt_pairs = []
                        for item in data:
                            if not item['symbol'].endswith('USDT'):
                                continue
                            try:
                                change = float(item['priceChangePercent'])
                            except (KeyError, TypeError, ValueError):
                                continue
                            item = dict(item)
                            item['_change_float'] = change
                            usdt_pairs.append(item)

                        sorted_pairs = sorted(
                            usdt_pairs,
                            key=lambda x: x['_change_float'],
                            reverse=True
                        )

                        top_gainers = sorted_pairs[:5]

                        negative_pairs = [item for item in usdt_pairs if item['_change_float'] < 0]
                        top_losers = sorted(
                            negative_pairs,
                            key=lambda x: x['_change_float']
                        )[:5]
                        
                        return {
                            'top_gainers': [{
                                'symbol': item['symbol'].replace('USDT', ''),
                                'price': f"${float(item['lastPrice']):,.2f}",
                                'change': f"{item['_change_float']:.2f}%",
                                'volume': f"${float(item['volume']):,.0f}",
                                'type': 'crypto'
                            } for item in top_gainers],
                            'top_losers': [{
                                'symbol': item['symbol'].replace('USDT', ''),
                                'price': f"${float(item['lastPrice']):,.2f}",
                                'change': f"{item['_change_float']:.2f}%",
                                'volume': f"${float(item['volume']):,.0f}",
                                'type': 'crypto'
                            } for item in top_losers]
                        }
                    else:
                        raise Exception(f"Binance API returned status {response.status}")
                        
        except Exception as e:
            print(f"Error getting Binance top performers: {e}")
            return {'top_gainers': [], 'top_losers': []}

    async def get_binance_price(self, symbol: str) -> Optional[Dict]:
        """Obtener precio de Binance con cache"""
        cache_key = f"binance_{symbol}"
        current_time = time.time()
        
        # Verificar cache
        if (cache_key in self.binance_cache and 
            current_time - self.binance_cache[cache_key]['timestamp'] < self.cache_timeout):
            return self.binance_cache[cache_key]['data']
        
        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            params = {'symbol': f'{symbol}USDT'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        price_data = {
                            'price': float(data['lastPrice']),
                            'change': float(data['priceChangePercent']),
                            'high': float(data['highPrice']),
                            'low': float(data['lowPrice']),
                            'volume': float(data['volume']),
                            'source': 'Binance',
                            'timestamp': current_time
                        }
                        
                        # Actualizar cache
                        self.binance_cache[cache_key] = {
                            'data': price_data,
                            'timestamp': current_time
                        }
                        
                        return price_data
                    else:
                        print(f"Binance API error for {symbol}: Status {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Binance API error for {symbol}: {e}")
            return None

    async def get_binance_orderbook(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        """Obtener orderbook de Binance"""
        try:
            url = f"{self.base_urls['binance']}/depth"
            params = {'symbol': f'{symbol}USDT', 'limit': limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'bids': [[float(price), float(quantity)] for price, quantity in data['bids'][:limit]],
                            'asks': [[float(price), float(quantity)] for price, quantity in data['asks'][:limit]],
                            'lastUpdateId': data['lastUpdateId']
                        }
                    else:
                        print(f"Binance orderbook error for {symbol}: Status {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Binance orderbook error for {symbol}: {e}")
            return None

    async def get_binance_klines(self, symbol: str, interval: str = '1h', limit: int = 24) -> Optional[List]:
        """Obtener datos de velas (klines) de Binance"""
        try:
            url = f"{self.base_urls['binance']}/klines"
            params = {
                'symbol': f'{symbol}USDT',
                'interval': interval,
                'limit': limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [{
                            'time': kline[0],
                            'open': float(kline[1]),
                            'high': float(kline[2]),
                            'low': float(kline[3]),
                            'close': float(kline[4]),
                            'volume': float(kline[5])
                        } for kline in data]
                    else:
                        print(f"Binance klines error for {symbol}: Status {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Binance klines error for {symbol}: {e}")
            return None

    async def get_price(self, symbol: str, asset_type: str = None) -> Optional[Dict]:
        """Obtener precio de un activo específico - Versión mejorada con Binance"""
        try:
            # Si no se especifica asset_type, detectarlo automáticamente
            if asset_type is None:
                asset_type = await self.detect_asset_type(symbol)
            
            if asset_type == 'crypto':
                # Priorizar Binance para cripto
                price_data = await self.get_binance_price(symbol)
                if not price_data:
                    # Fallback a otras fuentes
                    price_data = await self.get_crypto_price_parallel(symbol)
            else:
                price_data = await self.get_stock_price_parallel(symbol)
                
            if price_data:
                return {
                    'price': f"${price_data['price']:,.2f}",
                    'change': f"{'+' if price_data['change'] >= 0 else ''}{price_data['change']:.2f}%",
                    'high': f"${price_data.get('high', 0):,.2f}",
                    'low': f"${price_data.get('low', 0):,.2f}",
                    'volume': f"${price_data.get('volume', 0):,.0f}",
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
                self.get_binance_price(symbol),  # Ya implementado
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
            }  # ✅ CORREGIDO: Aquí estaba el error - corchete mal cerrado
            
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
        crypto_symbols = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'AVAX', 'MATIC', 
                         'LTC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM', 'BCH', 'VET', 'TRX', 'FIL']
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
        # Ya implementado con Binance
        return []

    async def process_market_data(self, stock_data: List[Dict], crypto_data: List[Dict]) -> Dict:
        """Procesar datos de mercado para top performers - AHORA ES ASYNC"""
        # Si tenemos datos de Binance, usarlos
        if crypto_data and (crypto_data.get('top_gainers') or crypto_data.get('top_losers')):
            market_data = {
                'top_performers': crypto_data.get('top_gainers', [])[:5],
                'worst_performers': crypto_data.get('top_losers', [])[:5],
                'market_summary': {
                    'sp500': '+0.3%',  # Placeholder - integrar después
                    'nasdaq': '+0.8%', 
                    'dow_jones': '-0.2%',
                    'bitcoin_dominance': '52.3%'
                }
            }
            return market_data
        else:
            return await self.get_simulated_data()

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

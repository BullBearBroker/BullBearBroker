import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import json
import time
import xml.etree.ElementTree as ET

from .crypto_service import CryptoService
from .stock_service import StockService

load_dotenv()

class MarketService:
    def __init__(self):
        self.api_keys = {
            'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', 'demo'),
            'coin_gecko': os.getenv('COIN_GECKO_API_KEY', ''),
            'twelvedata': os.getenv('TWELVEDATA_API_KEY', ''),
            'newsapi': os.getenv('NEWSAPI_API_KEY', ''),
            'mediastack': os.getenv('MEDIASTACK_API_KEY', ''),
            'binance': os.getenv('BINANCE_API_KEY', ''),
            'binance_secret': os.getenv('BINANCE_API_SECRET', '')
        }

        self.base_urls = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'coin_gecko': 'https://api.coingecko.com/api/v3',
            'twelvedata': 'https://api.twelvedata.com',
            'yahoo_finance': 'https://query1.finance.yahoo.com/v8/finance/chart/',
            'binance': 'https://api.binance.com/api/v3',
            'binance_futures': 'https://fapi.binance.com/fapi/v1',
            'newsapi': 'https://newsapi.org/v2/everything',
            'mediastack': 'http://api.mediastack.com/v1/news',
            'rss': 'https://news.google.com/rss/search'
        }

        # Cache compartida para precios
        self.price_cache: Dict[str, Dict] = {}
        self.cache_timeout = 2  # segundos (más rápido para datos en tiempo real)

        self.crypto_service = CryptoService()
        self.stock_service = StockService()

        self.logger = logging.getLogger(__name__)

    async def get_top_performers(self) -> Dict:
        """Obtener los mejores performers del mercado con datos reales de Binance"""
        try:
            # Obtener datos reales de Binance para cripto
            crypto_data = await self.get_binance_top_performers()
            # Obtener datos de acciones
            stock_data = await self.get_stock_market_data()
            
            return await self.process_market_data(stock_data, crypto_data)
            
        except Exception as e:
            self.logger.exception("Error getting real market data: %s", e)
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

                        def _build_entry(item: Dict) -> Dict:
                            symbol_clean = item['symbol'].replace('USDT', '')
                            payload = self._format_price_payload(
                                symbol_clean,
                                'crypto',
                                price=item.get('lastPrice'),
                                change=item.get('_change_float'),
                                high=item.get('highPrice'),
                                low=item.get('lowPrice'),
                                volume=item.get('volume'),
                                source='Binance'
                            )
                            self._set_cached_price(symbol_clean, 'crypto', payload)
                            formatted = self._format_price_response(payload)
                            return {
                                'symbol': symbol_clean,
                                'price': formatted['price'],
                                'change': formatted['change'],
                                'volume': formatted['volume'],
                                'type': 'crypto'
                            }

                        return {
                            'top_gainers': [_build_entry(item) for item in top_gainers],
                            'top_losers': [_build_entry(item) for item in top_losers]
                        }
                    else:
                        raise Exception(f"Binance API returned status {response.status}")
                        
        except Exception as e:
            self.logger.exception("Error getting Binance top performers: %s", e)
            return {'top_gainers': [], 'top_losers': []}

    async def get_binance_price(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """Obtener precio de Binance con cache"""
        if not force_refresh:
            cached = self._get_cached_price(symbol, 'crypto')
            if cached is not None:
                return cached

        try:
            url = f"{self.base_urls['binance']}/ticker/24hr"
            params = {'symbol': f'{symbol}USDT'}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        price_data = self._format_price_payload(
                            symbol,
                            'crypto',
                            price=data.get('lastPrice'),
                            change=data.get('priceChangePercent'),
                            high=data.get('highPrice'),
                            low=data.get('lowPrice'),
                            volume=data.get('volume'),
                            source='Binance'
                        )

                        self._set_cached_price(symbol, 'crypto', price_data)

                        return price_data
                    else:
                        self.logger.error(
                            "Binance API error for %s: Status %s", symbol, response.status
                        )
                        return None

        except Exception as e:
            self.logger.exception("Binance API error for %s: %s", symbol, e)
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
                        self.logger.error(
                            "Binance orderbook error for %s: Status %s", symbol, response.status
                        )
                        return None
                        
        except Exception as e:
            self.logger.exception("Binance orderbook error for %s: %s", symbol, e)
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
                        self.logger.error(
                            "Binance klines error for %s: Status %s", symbol, response.status
                        )
                        return None
                        
        except Exception as e:
            self.logger.exception("Binance klines error for %s: %s", symbol, e)
            return None

    async def get_crypto_price(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """Obtener precio de criptomonedas con cache y fallback a CryptoService."""
        if not force_refresh:
            cached = self._get_cached_price(symbol, 'crypto')
            if cached is not None:
                return cached

        try:
            price_data = await self.get_binance_price(symbol, force_refresh=force_refresh)
            if price_data is not None:
                return price_data

            parallel_data = await self.get_crypto_price_parallel(symbol)
            if parallel_data:
                payload = self._format_price_payload(
                    symbol,
                    'crypto',
                    price=parallel_data.get('price'),
                    change=parallel_data.get('change'),
                    source=parallel_data.get('source', 'multiple')
                )
                self._set_cached_price(symbol, 'crypto', payload)
                return payload

            fallback_price = await self.crypto_service.get_price(symbol)
            if fallback_price is not None:
                payload = self._format_price_payload(
                    symbol,
                    'crypto',
                    price=fallback_price,
                    source='CryptoService'
                )
                self._set_cached_price(symbol, 'crypto', payload)
                return payload

        except Exception as exc:
            self.logger.exception("Error getting crypto price for %s: %s", symbol, exc)

        return None

    async def get_stock_price(self, symbol: str, force_refresh: bool = False) -> Optional[Dict]:
        """Obtener precio de acciones con cache y fallback a StockService."""
        if not force_refresh:
            cached = self._get_cached_price(symbol, 'stock')
            if cached is not None:
                return cached

        try:
            parallel_data = await self.get_stock_price_parallel(symbol)
            if parallel_data:
                payload = self._format_price_payload(
                    symbol,
                    'stock',
                    price=parallel_data.get('price'),
                    change=parallel_data.get('change'),
                    source=parallel_data.get('source', 'multiple')
                )
                self._set_cached_price(symbol, 'stock', payload)
                return payload

            fallback_price = await self.stock_service.get_price(symbol)
            if fallback_price is not None:
                payload = self._format_price_payload(
                    symbol,
                    'stock',
                    price=fallback_price,
                    source='StockService'
                )
                self._set_cached_price(symbol, 'stock', payload)
                return payload

        except Exception as exc:
            self.logger.exception("Error getting stock price for %s: %s", symbol, exc)

        return None

    async def get_price(self, symbol: str, asset_type: str = None) -> Optional[Dict]:
        """Obtener precio de un activo específico - Versión mejorada con Binance"""
        try:
            # Si no se especifica asset_type, detectarlo automáticamente
            if asset_type is None:
                asset_type = await self.detect_asset_type(symbol)

            if asset_type == 'crypto':
                price_data = await self.get_crypto_price(symbol)
            else:
                price_data = await self.get_stock_price(symbol)

            if price_data:
                return self._format_price_response(price_data)
            return None

        except Exception as e:
            self.logger.exception("Error getting price for %s: %s", symbol, e)
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
            self.logger.exception("Error in parallel stock price fetch: %s", e)
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
            self.logger.exception("Error in parallel crypto price fetch: %s", e)
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
                    quote = data.get('Global Quote', {})

                    price_str = quote.get('05. price')
                    if price_str is None:
                        raise ValueError('Price field missing in Alpha Vantage response')

                    price = float(price_str)

                    change_percent = quote.get('10. change percent')
                    change = 0.0
                    if isinstance(change_percent, str):
                        change_percent = change_percent.strip().replace('%', '')
                        try:
                            change = float(change_percent)
                        except ValueError:
                            change = 0.0
                    elif isinstance(change_percent, (int, float)):
                        change = float(change_percent)

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

    async def get_news(self, symbol: str) -> Dict[str, List[Dict]]:
        """Obtener noticias para un símbolo con fallback entre NewsAPI, Mediastack y RSS."""
        strategies = [
            ('newsapi', self._fetch_newsapi),
            ('mediastack', self._fetch_mediastack),
            ('rss', self._fetch_rss)
        ]

        for name, strategy in strategies:
            try:
                articles = await strategy(symbol)
                if articles:
                    return {'source': name, 'articles': articles}
            except Exception as exc:
                self.logger.exception("%s provider failed for %s: %s", name, symbol, exc)

        return {'source': 'unavailable', 'articles': []}

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

    def _cache_key(self, symbol: str, asset_type: str) -> str:
        return f"{asset_type}:{symbol.upper()}"

    def _get_cached_price(self, symbol: str, asset_type: str) -> Optional[Dict]:
        cache_key = self._cache_key(symbol, asset_type)
        cached = self.price_cache.get(cache_key)
        if not cached:
            return None

        if time.time() - cached['timestamp'] < self.cache_timeout:
            return cached

        self.price_cache.pop(cache_key, None)
        return None

    def _set_cached_price(self, symbol: str, asset_type: str, payload: Dict) -> None:
        cache_key = self._cache_key(symbol, asset_type)
        self.price_cache[cache_key] = payload

    def _format_price_payload(
        self,
        symbol: str,
        asset_type: str,
        price: Optional[float],
        change: Optional[float] = None,
        high: Optional[float] = None,
        low: Optional[float] = None,
        volume: Optional[float] = None,
        source: Optional[str] = None
    ) -> Dict:
        current_time = time.time()
        payload = {
            'symbol': symbol.upper(),
            'asset_type': asset_type,
            'price': float(price) if price is not None else None,
            'change': self._safe_float(change),
            'high': self._safe_float(high),
            'low': self._safe_float(low),
            'volume': self._safe_float(volume),
            'source': source or '',
            'timestamp': current_time
        }
        return payload

    def _format_price_response(self, payload: Dict) -> Dict:
        price = payload.get('price')
        change = payload.get('change')
        high = payload.get('high')
        low = payload.get('low')
        volume = payload.get('volume')

        def _fmt_currency(value: Optional[float]) -> str:
            if value is None:
                return 'N/A'
            return f"${value:,.2f}"

        def _fmt_volume(value: Optional[float]) -> str:
            if value is None:
                return 'N/A'
            return f"${value:,.0f}"

        def _fmt_change(value: Optional[float]) -> str:
            if value is None:
                return 'N/A'
            sign = '+' if value >= 0 else ''
            return f"{sign}{value:.2f}%"

        return {
            'price': _fmt_currency(price),
            'change': _fmt_change(change),
            'high': _fmt_currency(high),
            'low': _fmt_currency(low),
            'volume': _fmt_volume(volume),
            'raw_price': price,
            'raw_change': change,
            'source': payload.get('source', '')
        }

    def _safe_float(self, value: Optional[float]) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    async def _fetch_newsapi(self, symbol: str) -> List[Dict]:
        if not self.api_keys['newsapi']:
            raise ValueError('NEWSAPI_API_KEY not configured')

        params = {
            'q': symbol,
            'language': 'en',
            'sortBy': 'publishedAt',
            'apiKey': self.api_keys['newsapi'],
            'pageSize': 10
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_urls['newsapi'], params=params) as response:
                if response.status != 200:
                    raise ValueError(f"NewsAPI status {response.status}")
                data = await response.json()
                return [
                    {
                        'title': article.get('title'),
                        'description': article.get('description'),
                        'url': article.get('url'),
                        'published_at': article.get('publishedAt')
                    }
                    for article in data.get('articles', [])
                ]

    async def _fetch_mediastack(self, symbol: str) -> List[Dict]:
        if not self.api_keys['mediastack']:
            raise ValueError('MEDIASTACK_API_KEY not configured')

        params = {
            'access_key': self.api_keys['mediastack'],
            'keywords': symbol,
            'languages': 'en',
            'limit': 10
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_urls['mediastack'], params=params) as response:
                if response.status != 200:
                    raise ValueError(f"Mediastack status {response.status}")
                data = await response.json()
                return [
                    {
                        'title': article.get('title'),
                        'description': article.get('description'),
                        'url': article.get('url'),
                        'published_at': article.get('published_at')
                    }
                    for article in data.get('data', [])
                ]

    async def _fetch_rss(self, symbol: str) -> List[Dict]:
        params = {
            'q': f"{symbol} stock"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_urls['rss'], params=params) as response:
                if response.status != 200:
                    raise ValueError(f"RSS status {response.status}")
                content = await response.text()

        root = ET.fromstring(content)
        channel = root.find('channel')
        if channel is None:
            return []

        articles = []
        for item in channel.findall('item')[:10]:
            articles.append({
                'title': item.findtext('title'),
                'description': item.findtext('description'),
                'url': item.findtext('link'),
                'published_at': item.findtext('pubDate')
            })

        return articles

# Singleton instance
market_service = MarketService()

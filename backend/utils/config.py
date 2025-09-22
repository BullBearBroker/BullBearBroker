import os
from secrets import token_urlsafe

from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

class Config:
    # Stocks APIs
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
    TWELVEDATA_API_KEY = os.getenv('TWELVEDATA_API_KEY')
    
    # Crypto APIs
    COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')
    COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY')
    REDIS_URL = os.getenv('BULLBEARBROKER_REDIS_URL')
    CRYPTO_PRICE_CACHE_TTL = int(os.getenv('CRYPTO_PRICE_CACHE_TTL', '60'))
    CRYPTO_HTTP_TIMEOUT = float(os.getenv('CRYPTO_HTTP_TIMEOUT', '10'))
    CRYPTO_HTTP_RETRIES = int(os.getenv('CRYPTO_HTTP_RETRIES', '2'))
    CRYPTO_HTTP_BACKOFF_BASE = float(os.getenv('CRYPTO_HTTP_BACKOFF_BASE', '0.5'))
    
    # News APIs
    NEWSAPI_API_KEY = os.getenv('NEWSAPI_API_KEY')
    CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')

    # Authentication / security
    JWT_SECRET_KEY = os.getenv(
        'BULLBEARBROKER_SECRET_KEY',
        token_urlsafe(64)
    )
    JWT_ALGORITHM = os.getenv('BULLBEARBROKER_JWT_ALGORITHM', 'HS256')
    
    # Binance no necesita key
    # Yahoo Finance no necesita key
    # Twitter API necesita app registration


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

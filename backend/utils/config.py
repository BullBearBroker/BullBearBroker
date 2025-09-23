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

    # Redis cache
    REDIS_URL = os.getenv('REDIS_URL')

    # News APIs
    NEWSAPI_API_KEY = os.getenv('NEWSAPI_API_KEY')
    CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')
    MEDIASTACK_API_KEY = os.getenv('MEDIASTACK_API_KEY')
    FINFEED_API_KEY = os.getenv('FINFEED_API_KEY')

    # AI providers
    HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')
    HUGGINGFACE_MODEL = os.getenv(
        'HUGGINGFACE_MODEL',
        'meta-llama/Meta-Llama-3-8B-Instruct'
    )
    HUGGINGFACE_SENTIMENT_MODEL = os.getenv(
        'HUGGINGFACE_SENTIMENT_MODEL',
        'distilbert-base-uncased-finetuned-sst-2-english'
    )
    HUGGINGFACE_API_URL = os.getenv(
        'HUGGINGFACE_API_URL',
        'https://api-inference.huggingface.co/models'
    )
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')

    # Authentication / security
    JWT_SECRET_KEY = os.getenv(
        'BULLBEARBROKER_SECRET_KEY',
        token_urlsafe(64)
    )
    JWT_ALGORITHM = os.getenv('BULLBEARBROKER_JWT_ALGORITHM', 'HS256')

    # Notifications
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_DEFAULT_CHAT_ID = os.getenv('TELEGRAM_DEFAULT_CHAT_ID')
    
    # Binance no necesita key
    # Yahoo Finance no necesita key
    # Twitter API necesita app registration


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

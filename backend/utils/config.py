import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Stocks APIs
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
    TWELVEDATA_API_KEY = os.getenv('TWELVEDATA_API_KEY')
    
    # Crypto APIs  
    COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')
    COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY')
    
    # News APIs
    NEWSAPI_API_KEY = os.getenv('NEWSAPI_API_KEY')
    CRYPTOPANIC_API_KEY = os.getenv('CRYPTOPANIC_API_KEY')
    
    # Binance no necesita key
    # Yahoo Finance no necesita key
    # Twitter API necesita app registration
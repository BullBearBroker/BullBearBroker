"""Accesos rápidos a los servicios del backend."""

from .alert_service import AlertService, alert_service
from .forex_service import ForexService, forex_service
from .news_service import NewsService, news_service
from .sentiment_service import SentimentService, sentiment_service

__all__ = [
    "AlertService",
    "ForexService",
    "NewsService",
    "SentimentService",
    "alert_service",
    "forex_service",
    "news_service",
    "sentiment_service",
]

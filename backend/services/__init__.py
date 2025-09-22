"""Accesos rápidos a los servicios del backend."""

from .alert_service import AlertService, alert_service
from .forex_service import ForexService, forex_service
from .sentiment_service import SentimentService, sentiment_service

__all__ = [
    "AlertService",
    "ForexService",
    "SentimentService",
    "alert_service",
    "forex_service",
    "sentiment_service",
]

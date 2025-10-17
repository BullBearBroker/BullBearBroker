"""Accesos rápidos a los servicios del backend."""

from __future__ import annotations

import importlib
from typing import Any

_forex_module = importlib.import_module("backend.services.forex_service")
_market_module = importlib.import_module("backend.services.market_service")
_news_module = importlib.import_module("backend.services.news_service")
_sentiment_module = importlib.import_module("backend.services.sentiment_service")

ForexService = _forex_module.ForexService
MarketService = _market_module.MarketService
NewsService = _news_module.NewsService
SentimentService = _sentiment_module.SentimentService


class _ServiceExport:
    __slots__ = ("_module", "_instance")

    def __init__(self, module: Any, instance: Any) -> None:
        object.__setattr__(self, "_module", module)
        object.__setattr__(self, "_instance", instance)

    def __getattr__(self, name: str) -> Any:
        instance = object.__getattribute__(self, "_instance")
        module = object.__getattribute__(self, "_module")
        if hasattr(instance, name):
            return getattr(instance, name)
        return getattr(module, name)

    def __setattr__(self, name: str, value: Any) -> None:
        instance = object.__getattribute__(self, "_instance")
        module = object.__getattribute__(self, "_module")
        if hasattr(instance, name):
            setattr(instance, name, value)
        else:
            setattr(module, name, value)


forex_service = _ServiceExport(_forex_module, _forex_module.forex_service)
market_service = _ServiceExport(_market_module, _market_module.market_service)
news_service = _ServiceExport(_news_module, _news_module.news_service)
sentiment_service = _ServiceExport(
    _sentiment_module, _sentiment_module.sentiment_service
)

__all__ = [
    "AlertService",
    "ForexService",
    "MarketService",
    "NewsService",
    "SentimentService",
    "alert_service",
    "forex_service",
    "market_service",
    "news_service",
    "sentiment_service",
]


def __getattr__(name: str):
    if name in {"AlertService", "alert_service"}:
        from .alert_service import AlertService, alert_service

        return AlertService if name == "AlertService" else alert_service
    raise AttributeError(name)

import sys
from pathlib import Path
import asyncio

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / 'backend'

sys.path.append(str(ROOT_DIR))
sys.path.append(str(BACKEND_DIR))

from backend.services.market_service import MarketService


def test_get_crypto_price_uses_cache(monkeypatch):
    service = MarketService()
    payload = service._format_price_payload(
        'BTC',
        'crypto',
        price=50000.0,
        change=2.5,
        high=51000.0,
        low=49000.0,
        volume=1000000.0,
        source='mock'
    )

    call_counter = {'count': 0}

    async def fake_binance(symbol: str, force_refresh: bool = False):
        call_counter['count'] += 1
        service._set_cached_price(symbol, 'crypto', payload)
        return payload

    monkeypatch.setattr(service, 'get_binance_price', fake_binance)

    async def _run_test():
        result_first = await service.get_crypto_price('BTC', force_refresh=True)
        result_second = await service.get_crypto_price('BTC')

        assert result_first['price'] == pytest.approx(50000.0)
        assert result_second['price'] == pytest.approx(50000.0)
        assert call_counter['count'] == 1

    asyncio.run(_run_test())


def test_get_crypto_price_fallback_to_service(monkeypatch):
    service = MarketService()

    async def fail_binance(symbol: str, force_refresh: bool = False):
        return None

    async def empty_parallel(symbol: str):
        return None

    async def fake_crypto_price(symbol: str):
        return 123.45

    monkeypatch.setattr(service, 'get_binance_price', fail_binance)
    monkeypatch.setattr(service, 'get_crypto_price_parallel', empty_parallel)
    monkeypatch.setattr(service.crypto_service, 'get_price', fake_crypto_price)

    async def _run_test():
        result = await service.get_crypto_price('ETH', force_refresh=True)

        assert result is not None
        assert result['price'] == pytest.approx(123.45)
        assert result['source'] == 'CryptoService'

    asyncio.run(_run_test())


def test_get_stock_price_network_failure(monkeypatch):
    service = MarketService()

    async def fail_parallel(symbol: str):
        raise RuntimeError('network down')

    async def fail_service(symbol: str):
        raise RuntimeError('fallback down')

    monkeypatch.setattr(service, 'get_stock_price_parallel', fail_parallel)
    monkeypatch.setattr(service.stock_service, 'get_price', fail_service)

    async def _run_test():
        result = await service.get_stock_price('AAPL', force_refresh=True)
        assert result is None

    asyncio.run(_run_test())


def test_get_news_fallback(monkeypatch):
    service = MarketService()

    async def fail_newsapi(symbol: str):
        raise RuntimeError('boom')

    async def empty_mediastack(symbol: str):
        return []

    async def rss_articles(symbol: str):
        return [{'title': 'Fallback', 'url': 'http://example.com', 'published_at': 'now'}]

    monkeypatch.setattr(service, '_fetch_newsapi', fail_newsapi)
    monkeypatch.setattr(service, '_fetch_mediastack', empty_mediastack)
    monkeypatch.setattr(service, '_fetch_rss', rss_articles)

    async def _run_test():
        result = await service.get_news('TSLA')

        assert result['source'] == 'rss'
        assert result['articles'] == [{'title': 'Fallback', 'url': 'http://example.com', 'published_at': 'now'}]

    asyncio.run(_run_test())

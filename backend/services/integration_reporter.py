"""Utilities to emit a concise integration health report via logging."""

from __future__ import annotations

import logging
from typing import List, Tuple

try:  # pragma: no cover - execution context may vary in tests
    from backend.services.market_service import market_service
    from backend.services.forex_service import forex_service
    from backend.utils.config import Config
except ImportError:  # pragma: no cover - fallback for package layout
    from services.market_service import market_service  # type: ignore
    from services.forex_service import forex_service  # type: ignore
    from utils.config import Config  # type: ignore

LOGGER = logging.getLogger(__name__)


async def log_api_integration_report() -> None:
    """Log the runtime status of the core market integrations."""

    statuses: List[Tuple[str, str]] = []
    remediations: List[str] = []

    # Nota de corrección: registramos claves ausentes para dejar constancia de los
    # fallbacks que aplicamos automáticamente en las integraciones.
    if not Config.COINMARKETCAP_API_KEY:
        remediations.append(
            "CoinMarketCap sin API key; se usa CoinGecko/Binance como primario"
        )
    if not Config.TWELVEDATA_API_KEY:
        remediations.append(
            "Twelve Data sin API key; Yahoo Finance queda como respaldo"
        )
    if not Config.ALPHA_VANTAGE_API_KEY:
        remediations.append(
            "Alpha Vantage sin API key; Yahoo Finance atiende stocks/forex"
        )

    # Binance (crypto tiempo real)
    try:
        binance_payload = await market_service.get_binance_price("BTC")
        if binance_payload:
            statuses.append((
                "Binance",
                f"ok precio={binance_payload.get('price')} fuente={binance_payload.get('source', 'N/D')}",
            ))
        else:
            statuses.append(("Binance", "sin datos (verificar símbolo o conexión)"))
    except Exception as exc:  # pragma: no cover - logging informativo
        statuses.append(("Binance", f"error {type(exc).__name__}: {exc}"))
        remediations.append("Se mantiene fallback CoinGecko en CryptoService")

    # Yahoo Finance (acciones/ETF)
    try:
        stock_payload = await market_service.get_stock_price("AAPL")
        if stock_payload:
            statuses.append((
                "Yahoo Finance",
                f"ok precio={stock_payload.get('price')} fuente={stock_payload.get('source', 'Yahoo Finance')}",
            ))
        else:
            statuses.append(("Yahoo Finance", "sin datos (respuesta vacía)") )
    except Exception as exc:  # pragma: no cover - logging informativo
        statuses.append(("Yahoo Finance", f"error {type(exc).__name__}: {exc}"))
        remediations.append("Revisar conectividad hacia query1.finance.yahoo.com")

    # Forex principal (pares FX)
    try:
        forex_payload = await forex_service.get_quote("EURUSD")
        if forex_payload:
            statuses.append((
                "Forex",
                f"ok precio={forex_payload.get('price')} fuente={forex_payload.get('source', 'Yahoo Finance')}",
            ))
        else:
            statuses.append(("Forex", "sin datos (pares no disponibles)"))
    except Exception as exc:  # pragma: no cover - logging informativo
        statuses.append(("Forex", f"error {type(exc).__name__}: {exc}"))
        remediations.append("Aplicar fallback manual usando Yahoo Finance")

    # Commodities vía servicio FX (ej: oro)
    try:
        commodities_payload = await forex_service.get_quote("XAUUSD")
        if commodities_payload:
            statuses.append((
                "Commodities",
                f"ok precio={commodities_payload.get('price')} fuente={commodities_payload.get('source', 'Yahoo Finance')}",
            ))
        else:
            statuses.append(("Commodities", "sin datos (verificar símbolo)"))
    except Exception as exc:  # pragma: no cover - logging informativo
        statuses.append(("Commodities", f"error {type(exc).__name__}: {exc}"))
        remediations.append("Utilizar XAU/USD vía Yahoo Finance como respaldo")

    summary = " | ".join(f"{name}: {status}" for name, status in statuses)
    LOGGER.info("Reporte integraciones APIs -> %s", summary)

    if remediations:
        LOGGER.info("Fallbacks aplicados: %s", " | ".join(remediations))


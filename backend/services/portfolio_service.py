"""Service helpers for portfolio management and analytics."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import contextmanager
from decimal import Decimal
from statistics import StatisticsError, fmean, stdev
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from backend.database import SessionLocal
from backend.models.portfolio import Portfolio, Position
from backend.schemas.portfolio import PortfolioCreate, PositionCreate
from backend.utils.config import Config

try:  # pragma: no cover - allow execution in different entrypoints
    from backend.services.market_service import MarketService, market_service
except ImportError:  # pragma: no cover
    MarketService = None  # type: ignore[assignment]
    market_service = None  # type: ignore[assignment]

try:  # pragma: no cover
    from backend.services.forex_service import forex_service
except ImportError:  # pragma: no cover
    forex_service = None  # type: ignore[assignment]


@contextmanager
def _session_scope(session_factory: sessionmaker = SessionLocal) -> Iterable[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - propagate after rollback
        session.rollback()
        raise
    finally:
        session.close()


def _normalize_name(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Portfolio name is required")
    return normalized


def _normalize_symbol(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        raise ValueError("Symbol is required")
    return normalized


def _to_decimal(value: float | int | Decimal) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (ValueError, TypeError) as exc:  # pragma: no cover - validation guard
        raise ValueError("Numeric value required") from exc
    return decimal_value


def create_portfolio(user_id: UUID, data: PortfolioCreate) -> Portfolio:
    name = _normalize_name(data.name)
    base_ccy = (data.base_ccy or "USD").strip().upper() or "USD"

    with _session_scope() as session:
        existing = session.scalar(
            select(Portfolio.id).where(
                Portfolio.user_id == user_id, Portfolio.name == name
            )
        )
        if existing is not None:
            raise ValueError("Portfolio name already exists for user")

        portfolio = Portfolio(user_id=user_id, name=name, base_ccy=base_ccy)
        session.add(portfolio)
        session.flush()
        session.refresh(portfolio)
        session.expunge(portfolio)
        return portfolio


def list_portfolios(user_id: UUID) -> list[Portfolio]:
    with _session_scope() as session:
        portfolios = (
            session.scalars(
                select(Portfolio)
                .options(selectinload(Portfolio.positions))
                .where(Portfolio.user_id == user_id)
                .order_by(Portfolio.created_at)
            )
            .unique()
            .all()
        )
        for portfolio in portfolios:
            for position in portfolio.positions:
                session.expunge(position)
            session.expunge(portfolio)
        return portfolios


def get_portfolio_owned(user_id: UUID, portfolio_id: UUID) -> Portfolio:
    with _session_scope() as session:
        portfolio = session.scalar(
            select(Portfolio)
            .options(selectinload(Portfolio.positions))
            .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        )
        if portfolio is None:
            raise ValueError("Portfolio not found")
        for position in portfolio.positions:
            session.expunge(position)
        session.expunge(portfolio)
        return portfolio


def add_position(portfolio_id: UUID, data: PositionCreate) -> Position:
    symbol = _normalize_symbol(data.symbol)
    quantity = _to_decimal(data.quantity)
    avg_price = _to_decimal(data.avg_price)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if avg_price < 0:
        raise ValueError("Average price cannot be negative")

    with _session_scope() as session:
        portfolio_exists = session.scalar(
            select(Portfolio.id).where(Portfolio.id == portfolio_id)
        )
        if portfolio_exists is None:
            raise ValueError("Portfolio not found")

        position = Position(
            portfolio_id=portfolio_id,
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
        )
        session.add(position)
        session.flush()
        session.refresh(position)
        session.expunge(position)
        return position


def get_position_owned(user_id: UUID, position_id: UUID) -> Position:
    with _session_scope() as session:
        position = session.scalar(
            select(Position)
            .options(selectinload(Position.portfolio))
            .where(Position.id == position_id)
        )
        if position is None or position.portfolio.user_id != user_id:
            raise ValueError("Position not found")
        session.expunge(position.portfolio)
        session.expunge(position)
        return position


def remove_position(position_id: UUID) -> None:
    with _session_scope() as session:
        result = session.execute(delete(Position).where(Position.id == position_id))
        if result.rowcount == 0:
            raise ValueError("Position not found")


async def _resolve_price(symbol: str) -> float | None:
    normalized = _normalize_symbol(symbol)
    if MarketService is not None:
        try:
            if Config.TESTING and isinstance(market_service, MarketService):
                return None
        except Exception:  # pragma: no cover - defensive fallback
            return None
    if market_service is not None:
        try:
            crypto = await market_service.get_crypto_price(normalized)
        except Exception:  # pragma: no cover - upstream logging
            crypto = None
        if crypto and crypto.get("price") is not None:
            try:
                return float(crypto["price"])
            except (TypeError, ValueError):
                pass

        try:
            stock = await market_service.get_stock_price(normalized)
        except Exception:  # pragma: no cover
            stock = None
        if stock and stock.get("price") is not None:
            try:
                return float(stock["price"])
            except (TypeError, ValueError):
                pass

    if forex_service is not None:
        try:
            fx_quote = await forex_service.get_quote(normalized)
        except Exception:  # pragma: no cover
            fx_quote = None
        if fx_quote and fx_quote.get("price") is not None:
            try:
                return float(fx_quote["price"])
            except (TypeError, ValueError):
                pass

    return None


async def valuate_portfolio(
    positions: list[Position], base_ccy: str = "USD"
) -> dict[str, float]:
    if not positions:
        return {"equity_value": 0.0, "pnl_abs": 0.0, "pnl_pct": 0.0}

    prices = await asyncio.gather(*(_resolve_price(pos.symbol) for pos in positions))

    equity_value = 0.0
    pnl_abs_total = 0.0
    cost_basis = 0.0

    for position, price in zip(positions, prices, strict=False):
        qty = float(position.quantity or 0)
        avg_price = float(position.avg_price or 0)
        if price is None:
            continue
        market_value = price * qty
        equity_value += market_value
        pnl_abs = (price - avg_price) * qty
        pnl_abs_total += pnl_abs
        if qty > 0 and avg_price > 0:
            cost_basis += avg_price * qty

    pnl_pct_total = pnl_abs_total / cost_basis if cost_basis > 0 else 0.0

    return {
        "equity_value": float(round(equity_value, 2)),
        "pnl_abs": float(round(pnl_abs_total, 2)),
        "pnl_pct": float(pnl_pct_total),
    }


def metrics(perf_series: list[float] | None) -> dict[str, float | None] | None:
    if not perf_series:
        return None

    daily = perf_series[-1]
    mtd = sum(perf_series[-21:]) if len(perf_series) >= 5 else None
    ytd = sum(perf_series) if len(perf_series) >= 50 else None

    return {"daily": daily, "mtd": mtd, "ytd": ytd}


def risk_metrics(
    returns: list[float] | None, rf: float = 0.0, equity: float | None = None
) -> dict[str, float | None] | None:
    if not returns or len(returns) < 2:
        return None

    try:
        volatility = stdev(returns)
    except StatisticsError:  # pragma: no cover - defensive guard
        return None

    sharpe = None
    if volatility > 0:
        sharpe = (fmean(returns) - rf) / volatility

    var_95 = None
    if equity is not None and volatility > 0:
        var_95 = float(-1.65 * volatility * equity)

    return {"sharpe": sharpe, "var_95": var_95}


def get_returns_series(positions: list[Position]) -> list[float] | None:
    """Placeholder until historical performance is integrated."""

    if not positions:
        return None
    return None


__all__ = [
    "create_portfolio",
    "list_portfolios",
    "get_portfolio_owned",
    "add_position",
    "remove_position",
    "get_position_owned",
    "valuate_portfolio",
    "metrics",
    "risk_metrics",
    "get_returns_series",
]

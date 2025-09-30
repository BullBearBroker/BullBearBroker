"""Service layer for user portfolio management."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from backend.database import SessionLocal
from backend.models.portfolio import PortfolioItem

try:  # pragma: no cover - compatibility with different entrypoints
    from backend.services.market_service import market_service
except ImportError:  # pragma: no cover
    from services.market_service import market_service  # type: ignore

try:  # pragma: no cover
    from backend.services.forex_service import forex_service
except ImportError:  # pragma: no cover
    from services.forex_service import forex_service  # type: ignore


class PortfolioItemNotFoundError(Exception):
    """Raised when attempting to delete a non-existent portfolio entry."""


class PortfolioService:
    """High level operations for managing user portfolios."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session_scope(self) -> Iterable[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------
    # CRUD helpers
    # ------------------------------
    def list_items(self, user_id: UUID) -> List[PortfolioItem]:
        with self._session_scope() as session:
            records = (
                session.scalars(
                    select(PortfolioItem).where(PortfolioItem.user_id == user_id)
                )
                .unique()
                .all()
            )
            for record in records:
                session.expunge(record)
            return records

    def create_item(self, user_id: UUID, *, symbol: str, amount: float) -> PortfolioItem:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("El símbolo es obligatorio")
        try:
            normalized_amount = float(amount)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("La cantidad debe ser numérica") from exc
        if normalized_amount <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")

        with self._session_scope() as session:
            item = PortfolioItem(
                user_id=user_id,
                symbol=normalized_symbol,
                amount=Decimal(str(normalized_amount)),
            )
            session.add(item)
            session.flush()
            session.refresh(item)
            session.expunge(item)
            return item

    def delete_item(self, user_id: UUID, item_id: UUID) -> bool:
        with self._session_scope() as session:
            stmt = (
                delete(PortfolioItem)
                .where(PortfolioItem.user_id == user_id)
                .where(PortfolioItem.id == item_id)
            )
            result = session.execute(stmt)
            return result.rowcount > 0

    # ------------------------------
    # Valuation helpers
    # ------------------------------
    async def get_portfolio_overview(self, user_id: UUID) -> Dict[str, Any]:
        items = self.list_items(user_id)
        if not items:
            return {"items": [], "total_value": 0.0}

        prices = await asyncio.gather(
            *[self._resolve_price(item.symbol) for item in items]
        )

        overview_items: List[Dict[str, Any]] = []
        total_value = 0.0
        for item, price in zip(items, prices):
            amount_float = float(item.amount)
            value = price * amount_float if price is not None else None
            if value is not None:
                total_value += value
            overview_items.append(
                {
                    "id": item.id,
                    "symbol": item.symbol,
                    "amount": amount_float,
                    "price": price,
                    "value": value,
                }
            )

        return {
            "items": overview_items,
            "total_value": round(total_value, 2),
        }

    async def _resolve_price(self, symbol: str) -> Optional[float]:
        normalized = symbol.strip().upper()
        # Try crypto first
        if market_service is not None:
            try:
                crypto = await market_service.get_crypto_price(normalized)
            except Exception:  # pragma: no cover - defensive logging happens upstream
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
                fx = await forex_service.get_quote(normalized)
            except Exception:  # pragma: no cover
                fx = None
            if fx and fx.get("price") is not None:
                try:
                    return float(fx["price"])
                except (TypeError, ValueError):
                    pass

        return None


portfolio_service = PortfolioService()

__all__ = ["PortfolioService", "portfolio_service", "PortfolioItemNotFoundError"]

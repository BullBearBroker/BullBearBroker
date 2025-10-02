"""Service layer for user portfolio management."""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import Iterable
from contextlib import contextmanager
from decimal import Decimal
from typing import Any
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

    MAX_IMPORT_ROWS = 500
    MAX_IMPORT_BYTES = 256 * 1024  # 256 KiB

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
    def list_items(self, user_id: UUID) -> list[PortfolioItem]:
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

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        cleaned = str(symbol or "").strip().upper()
        if not cleaned:
            raise ValueError("El símbolo es obligatorio")
        return cleaned

    def create_item(self, user_id: UUID, *, symbol: str, amount: float) -> PortfolioItem:
        normalized_symbol = self._normalize_symbol(symbol)
        try:
            normalized_amount = float(amount)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("La cantidad debe ser numérica") from exc
        if normalized_amount <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")

        with self._session_scope() as session:
            existing = session.scalar(
                select(PortfolioItem.id)
                .where(PortfolioItem.user_id == user_id)
                .where(PortfolioItem.symbol == normalized_symbol)
            )
            if existing is not None:
                raise ValueError("El símbolo ya existe en tu portafolio")

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
    # CSV helpers
    # ------------------------------
    def export_to_csv(self, user_id: UUID) -> str:
        items = self.list_items(user_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["symbol", "amount"])
        for item in items:
            writer.writerow([item.symbol, float(item.amount)])
        return buffer.getvalue()

    def import_from_csv(self, user_id: UUID, *, content: str) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("El archivo CSV está vacío")

        content = content.lstrip("\ufeff")

        if len(content.encode("utf-8")) > self.MAX_IMPORT_BYTES:
            raise ValueError(
                "El archivo CSV supera el tamaño máximo permitido de 256KB"
            )

        stream = io.StringIO(content)
        sample = stream.read(1024)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(stream, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("El CSV debe incluir encabezados")

        normalized_headers = {
            name.strip().lower().lstrip("\ufeff"): name for name in reader.fieldnames if name
        }
        required = {"symbol", "amount"}
        missing = required - normalized_headers.keys()
        if missing:
            raise ValueError(
                "Faltan columnas requeridas en el CSV: " + ", ".join(sorted(missing))
            )

        errors: list[dict[str, Any]] = []
        created_items: list[PortfolioItem] = []
        seen_symbols: set[str] = set()

        with self._session_scope() as session:
            existing_symbols: set[str] = {
                row[0]
                for row in session.execute(
                    select(PortfolioItem.symbol).where(PortfolioItem.user_id == user_id)
                )
            }

            for index, row in enumerate(reader, start=2):
                if index - 1 > self.MAX_IMPORT_ROWS:
                    errors.append(
                        {
                            "row": index,
                            "message": "El archivo CSV supera el máximo de 500 filas",
                        }
                    )
                    break

                if not row:
                    continue

                raw_symbol = row.get(normalized_headers["symbol"], "")
                raw_amount = row.get(normalized_headers["amount"], "")

                if raw_symbol is None and raw_amount is None:
                    continue

                try:
                    normalized_symbol = self._normalize_symbol(raw_symbol)
                except ValueError as exc:
                    errors.append({"row": index, "message": str(exc)})
                    continue

                duplicate_in_file = normalized_symbol in seen_symbols
                seen_symbols.add(normalized_symbol)

                if normalized_symbol in existing_symbols:
                    errors.append(
                        {
                            "row": index,
                            "message": "El símbolo ya existe en tu portafolio",
                        }
                    )
                    continue

                if duplicate_in_file:
                    errors.append(
                        {
                            "row": index,
                            "message": "Símbolo duplicado en el archivo",
                        }
                    )
                    continue

                try:
                    amount_value = float(str(raw_amount).strip())
                except (TypeError, ValueError):
                    errors.append({"row": index, "message": "La cantidad debe ser numérica"})
                    continue

                if amount_value <= 0:
                    errors.append(
                        {"row": index, "message": "La cantidad debe ser mayor que cero"}
                    )
                    continue

                item = PortfolioItem(
                    user_id=user_id,
                    symbol=normalized_symbol,
                    amount=Decimal(str(amount_value)),
                )
                session.add(item)
                session.flush()
                session.refresh(item)
                session.expunge(item)

                created_items.append(item)
                existing_symbols.add(normalized_symbol)

        return {
            "created": len(created_items),
            "items": [
                {
                    "id": item.id,
                    "symbol": item.symbol,
                    "amount": float(item.amount),
                }
                for item in created_items
            ],
            "errors": errors,
        }

    # ------------------------------
    # Valuation helpers
    # ------------------------------
    async def get_portfolio_overview(self, user_id: UUID) -> dict[str, Any]:
        items = self.list_items(user_id)
        if not items:
            return {"items": [], "total_value": 0.0}

        prices = await asyncio.gather(
            *[self._resolve_price(item.symbol) for item in items]
        )

        overview_items: list[dict[str, Any]] = []
        total_value = 0.0
        for item, price in zip(items, prices, strict=False):
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

    async def _resolve_price(self, symbol: str) -> float | None:
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

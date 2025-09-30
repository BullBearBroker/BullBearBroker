"""Portfolio item model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # pragma: no cover - import resolution for different entrypoints
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from .user import User


class PortfolioItem(Base):
    """Represents a single asset held by a user portfolio."""

    __tablename__ = "portfolio_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="portfolio_items", lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"PortfolioItem(id={self.id!s}, symbol={self.symbol!r}, "
            f"amount={self.amount!s})"
        )


__all__ = ["PortfolioItem"]

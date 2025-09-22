from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class Alert(Base):
    """Alerta asociada a un usuario."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    comparison: Mapped[str] = mapped_column(String(10), default="above", nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="websocket")
    message: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="alerts")

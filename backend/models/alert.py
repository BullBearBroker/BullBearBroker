from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (  # [Codex] cambiado - añadir Boolean
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.models.user import User

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class Alert(Base):
    """Alerta asociada a un usuario."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # [Codex] nuevo - título visible en frontend
    asset: Mapped[str] = mapped_column(String(50), nullable=False)
    condition: Mapped[str] = mapped_column(String(255), default=">", nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # [Codex] nuevo - estado de alerta
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="alerts")

from __future__ import annotations

# isort: skip_file

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    event,
)
from sqlalchemy import (  # isort: skip
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from backend.models.user import User

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class AlertDeliveryMethod(str, Enum):
    """Available delivery channels for an alert."""

    PUSH = "push"
    EMAIL = "email"
    INAPP = "inapp"
    WEBHOOK = "webhook"


class Alert(Base):
    """Advanced alert configuration stored per user."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Nueva configuración avanzada
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    delivery_method: Mapped[AlertDeliveryMethod] = mapped_column(
        SQLEnum(
            AlertDeliveryMethod,
            name="alert_delivery_method",
            native_enum=False,
        ),
        nullable=False,
        default=AlertDeliveryMethod.PUSH,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pending_delivery: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Campos heredados para compatibilidad con versiones anteriores
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset: Mapped[str | None] = mapped_column(String(50), nullable=True)
    condition_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="alerts")

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - helper para depuración
        return {
            "id": str(self.id),
            "name": self.name,
            "condition": self.condition,
            "delivery_method": self.delivery_method.value,
            "active": self.active,
            "pending_delivery": self.pending_delivery,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@event.listens_for(Alert, "before_insert", propagate=True)
def _ensure_alert_name(
    mapper, connection, target
) -> None:  # pragma: no cover - simple guard
    del mapper, connection
    name = (getattr(target, "name", "") or "").strip()
    if name:
        target.name = name
        return

    fallback = (getattr(target, "title", "") or "").strip()
    if not fallback:
        fallback = (getattr(target, "asset", "") or "").strip()
    target.name = fallback or "Alert"

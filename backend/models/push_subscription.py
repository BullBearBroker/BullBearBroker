"""Model definition for browser push notification subscriptions."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # pragma: no cover - compatibility with different import paths
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class PushSubscription(Base):
    """Stores a Web Push subscription for a user."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="push_subscriptions")


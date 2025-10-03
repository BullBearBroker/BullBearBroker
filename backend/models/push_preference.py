"""Model to persist user-level push notification preferences."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.user import User

try:  # pragma: no cover - import alias compatibility
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class PushNotificationPreference(Base):
    """Stores user choices about which push categories to receive."""

    __tablename__ = "push_notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_push_notification_preferences_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    news_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    system_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="push_preferences")


__all__ = ["PushNotificationPreference"]

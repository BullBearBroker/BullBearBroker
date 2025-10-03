import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]

if TYPE_CHECKING:
    from backend.models.user import User

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint = Column(String, nullable=False, unique=True)
    auth = Column(String, nullable=False)
    p256dh = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="push_subscriptions")

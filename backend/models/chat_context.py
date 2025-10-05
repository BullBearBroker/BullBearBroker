from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

try:  # pragma: no cover - support multiple import paths
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]


class ChatContext(Base):
    __tablename__ = "chat_context"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    user_id = Column(String, index=True, nullable=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

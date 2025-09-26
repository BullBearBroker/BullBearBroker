from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from backend.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # ✅ id ahora es UUID real en la DB
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # ✅ soporte para expiración opcional

    user = relationship("User", back_populates="refresh_tokens", lazy="joined")

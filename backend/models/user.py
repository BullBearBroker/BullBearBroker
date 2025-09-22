from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from utils.config import password_context

if TYPE_CHECKING:
    from .alert import Alert
    from .session import UserSession


class User(Base):
    """Modelo persistente de usuario."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    subscription_level: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    api_calls_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reset: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def verify_password(self, password: str) -> bool:
        """Verificar si la contraseña coincide."""
        return password_context.verify(password, self.hashed_password)

    def reset_api_counter(self) -> None:
        """Resetear el contador de llamadas diarias si cambió la fecha."""
        now = datetime.utcnow()
        if self.last_reset.date() < now.date():
            self.api_calls_today = 0
            self.last_reset = now

    def to_dict(self) -> dict:
        """Representación serializable del usuario."""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "subscription_level": self.subscription_level,
            "api_calls_today": self.api_calls_today,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_reset": self.last_reset.isoformat() if self.last_reset else None,
        }


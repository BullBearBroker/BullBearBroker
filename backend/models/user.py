from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # pragma: no cover
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]

try:  # pragma: no cover
    from utils.config import password_context
except ImportError:  # pragma: no cover
    from backend.utils.config import password_context  # type: ignore[no-redef]


class User(Base):
    """Modelo persistente de usuario."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    subscription_level: Mapped[str] = mapped_column(String, default="free", nullable=False)
    api_calls_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reset: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
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

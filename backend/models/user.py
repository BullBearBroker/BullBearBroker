from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from utils.config import password_context

Base = declarative_base()


class User(Base):
    """Modelo persistente de usuario."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    subscription_level = Column(String, default="free", nullable=False)
    api_calls_today = Column(Integer, default=0, nullable=False)
    last_reset = Column(DateTime, default=datetime.utcnow, nullable=False)

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

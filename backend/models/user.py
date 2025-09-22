from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, Float
from sqlalchemy.orm import relationship

from .base import Base


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

    alerts = relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def verify_password(self, password: str) -> bool:
        """Verificar si la contraseña coincide."""
        from utils.config import password_context

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


class Alert(Base):
    """Alerta configurada por un usuario."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    asset_type = Column(String, nullable=True)
    condition_type = Column(String, nullable=False)
    threshold_value = Column(Float, nullable=False)
    is_repeating = Column(Boolean, default=False, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    triggered_at = Column(DateTime, nullable=True)
    last_triggered_price = Column(Float, nullable=True)

    user = relationship("User", back_populates="alerts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "asset_type": self.asset_type,
            "condition_type": self.condition_type,
            "threshold_value": self.threshold_value,
            "is_repeating": self.is_repeating,
            "active": self.active,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "last_triggered_price": self.last_triggered_price,
        }


class UserSession(Base):
    """Sesión persistente del usuario para gestionar tokens."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="sessions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token": self.token,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
        }

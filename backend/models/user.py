from __future__ import annotations

from datetime import datetime
import uuid
from enum import Enum as PyEnum  # [Codex] nuevo
from typing import TYPE_CHECKING, Optional  # [Codex] cambiado - se usa Optional

from sqlalchemy import DateTime, Enum, String  # [Codex] cambiado - se añade Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .refresh_token import RefreshToken
    from .portfolio import PortfolioItem

try:  # pragma: no cover
    from .base import Base
except ImportError:  # pragma: no cover
    from backend.models.base import Base  # type: ignore[no-redef]

# 🔧 Ajuste: import consistente para evitar error con `utils`
try:  # pragma: no cover
    from backend.utils.config import password_context
except ImportError:  # pragma: no cover
    from backend.utils.config import password_context  # type: ignore[no-redef]


class RiskProfile(PyEnum):  # [Codex] nuevo
    CONSERVADOR = "conservador"
    MODERADO = "moderado"
    AGRESIVO = "agresivo"


class User(Base):
    """Modelo persistente de usuario."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    risk_profile: Mapped[Optional[str]] = mapped_column(  # [Codex] nuevo
        Enum(RiskProfile, name="risk_profile_enum", native_enum=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    portfolio_items: Mapped[list["PortfolioItem"]] = relationship(
        "PortfolioItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def verify_password(self, password: str) -> bool:
        """Verificar si la contraseña coincide."""
        return password_context.verify(password, self.password_hash)

    def to_dict(self) -> dict:
        """Representación serializable del usuario."""
        return {
            "id": str(self.id) if self.id else None,
            "email": self.email,
            "risk_profile": self.risk_profile,  # [Codex] nuevo
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

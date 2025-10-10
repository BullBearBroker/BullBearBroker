# 🧩 Bloque 9A
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field  # CODEx: Field permite defaults dinámicos


class NotificationEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)  # CODEx: generar UUID único por evento
    title: str
    body: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )  # CODEx: garantizar marca temporal en UTC consciente
    # Campo libre para metadatos opcionales (tipo, prioridad, etc.)
    meta: dict[str, Any] | None = None

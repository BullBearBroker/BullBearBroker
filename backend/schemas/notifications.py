# 🧩 Bloque 9A
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel


class NotificationEvent(BaseModel):
    id: UUID = uuid4()
    title: str
    body: str
    timestamp: datetime = datetime.now(UTC)
    # Campo libre para metadatos opcionales (tipo, prioridad, etc.)
    meta: dict[str, Any] | None = None

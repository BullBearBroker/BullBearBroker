# 🧩 Bloque 9A
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4


class NotificationEvent(BaseModel):
    id: UUID = uuid4()
    title: str
    body: str
    timestamp: datetime = datetime.now(timezone.utc)
    # Campo libre para metadatos opcionales (tipo, prioridad, etc.)
    meta: Optional[dict[str, Any]] = None

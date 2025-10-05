from backend.core.logging_config import get_logger
from backend.database import SessionLocal
from backend.models.chat_context import ChatContext

logger = get_logger(service="context_service")


def save_message(session_id: str, message: str, response: str) -> None:
    db = SessionLocal()
    try:
        record = ChatContext(session_id=session_id, message=message, response=response)
        db.add(record)
        db.commit()
        logger.info({"event": "context_saved", "session": session_id, "length": len(message)})
    finally:
        db.close()


def get_history(session_id: str):
    db = SessionLocal()
    try:
        return (
            db.query(ChatContext)
            .filter(ChatContext.session_id == session_id)
            .order_by(ChatContext.created_at)
            .all()
        )
    finally:
        db.close()

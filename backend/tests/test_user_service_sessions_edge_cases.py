import hashlib
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.security import create_refresh_token
from backend.models import Base, RefreshToken, Session
from backend.services import user_service as user_service_module
from backend.services.user_service import InvalidTokenError, UserService
from backend.utils.config import Config


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def service(session_factory, monkeypatch: pytest.MonkeyPatch) -> UserService:
    monkeypatch.setattr(user_service_module, "SessionLocal", session_factory)
    return UserService(
        session_factory=session_factory, secret_key="secret", algorithm="HS256"
    )


def test_get_current_user_rejects_expired_session(
    service: UserService, session_factory
) -> None:
    user = service.create_user("expired@example.com", "secret")
    token, session_record = service.create_session(
        user.id, expires_in=timedelta(minutes=5)
    )

    with session_factory() as session:
        stored = session.get(Session, session_record.id)
        assert stored is not None
        stored.expires_at = datetime.utcnow() - timedelta(minutes=1)
        session.commit()

    with pytest.raises(InvalidTokenError):
        service.get_current_user(token)


def test_rotate_refresh_token_replaces_database_record(
    service: UserService, session_factory
) -> None:
    user = service.create_user("rotate2@example.com", "secret")
    token = create_refresh_token(sub=str(user.id))
    stored = service.store_refresh_token(user.id, token)

    with session_factory() as session:
        db_token = session.get(RefreshToken, stored.id)
        assert db_token is not None

    time.sleep(1)

    new_user, new_token, expires_at = service.rotate_refresh_token(token)

    assert new_user.id == user.id
    assert new_token != token
    assert expires_at.tzinfo == UTC

    with session_factory() as session:
        tokens = (
            session.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()
        )
        assert len(tokens) == 1
        assert tokens[0].token == new_token


def test_revoke_all_refresh_tokens_removes_in_memory_records(
    service: UserService,
) -> None:
    user = service.create_user("revoke@example.com", "secret")
    token1, _ = service.create_refresh_token(user.id)
    token2, _ = service.create_refresh_token(user.id)

    assert token1 in service._in_memory_refresh_tokens
    assert token2 in service._in_memory_refresh_tokens

    service.revoke_all_refresh_tokens(user.id)

    assert token1 not in service._in_memory_refresh_tokens
    assert token2 not in service._in_memory_refresh_tokens


def test_register_external_session_evicts_oldest(
    service: UserService, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "MAX_CONCURRENT_SESSIONS", 2, raising=False)

    events: list[dict] = []

    def _capture_event(logger, **payload):  # noqa: ANN001 - align with log_event
        events.append(payload)

    monkeypatch.setattr(user_service_module, "log_event", _capture_event)

    user = service.create_user("sessions@example.com", "secret")
    base = datetime.now(UTC)

    service.register_external_session(user.id, "token-0", base + timedelta(minutes=5))
    service.register_external_session(user.id, "token-1", base + timedelta(minutes=10))
    service.register_external_session(user.id, "token-2", base + timedelta(minutes=15))

    with session_factory() as session:
        stored = (
            session.query(Session)
            .filter(Session.user_id == user.id)
            .order_by(Session.created_at.asc())
            .all()
        )
        assert len(stored) == 2
        tokens = {record.token for record in stored}
        assert tokens == {"token-1", "token-2"}

    hashed = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()[:8]
    evicted_events = [evt for evt in events if evt.get("event") == "session_evicted"]
    assert evicted_events
    assert evicted_events[0].get("user_id_hash") == hashed

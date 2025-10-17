from datetime import datetime, timedelta
from uuid import uuid4

import pytest

# QA: marcamos este módulo slow por recrear engines SQLite en memoria
pytestmark = pytest.mark.slow
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.security import create_refresh_token
from backend.models import Base, RefreshToken, Session
from backend.services import user_service as user_service_module
from backend.services.user_service import UserService


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


def test_create_user_invalid_risk_profile_raises(service: UserService) -> None:
    with pytest.raises(ValueError):
        service.create_user("invalid@example.com", "pass123", risk_profile="extremo")


def test_rotate_refresh_token_rejects_expired(
    service: UserService, session_factory
) -> None:
    user = service.create_user("rotate@example.com", "secret")
    token = create_refresh_token(sub=str(user.id))
    stored = service.store_refresh_token(user.id, token)

    with session_factory() as session:
        db_token = session.get(RefreshToken, stored.id)
        assert db_token is not None
        db_token.expires_at = datetime.utcnow() - timedelta(days=1)
        session.commit()

    with pytest.raises(HTTPException) as exc:
        service.rotate_refresh_token(token)

    assert exc.value.status_code == 401
    assert exc.value.detail == "refresh_expired"


def test_revoke_all_refresh_tokens_clears_in_memory_store(service: UserService) -> None:
    user = service.create_user("tokens@example.com", "secret")
    token, _ = service.create_refresh_token(user.id)
    service._in_memory_refresh_tokens[token].expires_at = datetime.utcnow() + timedelta(
        minutes=5
    )

    assert token in service._in_memory_refresh_tokens
    service.revoke_all_refresh_tokens(user.id)
    assert token not in service._in_memory_refresh_tokens


def test_multiple_sessions_recorded(service: UserService, session_factory) -> None:
    user = service.create_user("sessions@example.com", "secret")

    token1, session1 = service.create_session(user.id)
    with session_factory() as session:
        manual_session = Session(
            id=uuid4(),
            user_id=user.id,
            token="manual-token",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        session.add(manual_session)
        session.commit()

    sessions = service.get_active_sessions(user.id)
    assert {sess.id for sess in sessions} == {session1.id, manual_session.id}


def test_logout_invalidates_sessions(service: UserService, session_factory) -> None:
    user = service.create_user("logout@example.com", "secret")
    token, session_record = service.create_session(user.id)

    with session_factory() as session:
        stored_session = session.get(Session, session_record.id)
        assert stored_session is not None
        stored_session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        session.commit()

    active_sessions = service.get_active_sessions(user.id)
    assert active_sessions == []

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.models import Base, RefreshToken, Session, User
from backend.services import user_service as user_service_module
from backend.services.user_service import InvalidTokenError, UserService


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
    return UserService(session_factory=session_factory, secret_key="secret", algorithm="HS256")


def test_create_user_with_invalid_risk_profile_does_not_touch_db(service: UserService, session_factory) -> None:
    with pytest.raises(ValueError):
        service.create_user("invalid@example.com", "secret", risk_profile="super-risky")

    with session_factory() as session:
        assert session.execute(select(User)).first() is None


def test_rotate_refresh_token_rejects_expired_entry(service: UserService, session_factory) -> None:
    user = service.create_user("refresh@example.com", "password123")
    refresh_token, _ = service.create_refresh_token(user.id)
    stored = service.store_refresh_token(user.id, refresh_token)

    with session_factory() as session:
        db_token = session.get(RefreshToken, stored.id)
        assert db_token is not None
        db_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        session.commit()

    with pytest.raises(HTTPException) as excinfo:
        service.rotate_refresh_token(refresh_token)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "refresh_expired"

    with session_factory() as session:
        assert session.get(RefreshToken, stored.id) is None


def test_revoke_all_refresh_tokens_clears_memory_even_when_empty(service: UserService, session_factory) -> None:
    user = service.create_user("tokens@example.com", "secret")

    # Primera llamada sin tokens existentes debe ser segura
    service.revoke_all_refresh_tokens(user.id)

    token, _ = service.create_refresh_token(user.id)
    assert token in service._in_memory_refresh_tokens

    service.revoke_all_refresh_tokens(user.id)
    assert token not in service._in_memory_refresh_tokens

    with session_factory() as session:
        assert session.execute(select(RefreshToken)).first() is None


def test_get_current_user_rejects_expired_session(service: UserService, session_factory) -> None:
    user = service.create_user("session@example.com", "secret")
    token, session_record = service.create_session(user.id)

    with session_factory() as session:
        stored_session = session.get(Session, session_record.id)
        assert stored_session is not None
        stored_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    with pytest.raises(InvalidTokenError):
        service.get_current_user(token)

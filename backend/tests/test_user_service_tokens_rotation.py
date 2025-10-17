# ruff: noqa: I001
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

# QA: marcamos este módulo slow por manipular engine/fixtures compartidos
pytestmark = pytest.mark.slow
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.core.security import create_refresh_token
from backend.models import Base, RefreshToken, Session as SessionModel
from backend.routers.auth import LogoutRequest, logout
from backend.services import user_service as user_service_module
from backend.services.user_service import InvalidTokenError, UserService, _utcnow


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


def test_rotate_refresh_token_persists_new_entry(
    service: UserService, session_factory
) -> None:
    user = service.create_user("rotate-db@example.com", "secret")
    original_refresh = create_refresh_token(sub=str(user.id), jti=str(uuid4()))
    service.store_refresh_token(user.id, original_refresh)

    rotated_user, new_refresh, refresh_expires = service.rotate_refresh_token(
        original_refresh
    )

    assert rotated_user.id == user.id
    assert new_refresh != original_refresh
    assert refresh_expires.tzinfo is not None

    with session_factory() as session:
        rows = (
            session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].token == new_refresh


def test_rotate_refresh_token_removes_expired_record(
    service: UserService, session_factory
) -> None:
    user = service.create_user("expired-rotation@example.com", "secret")
    refresh_token = create_refresh_token(sub=str(user.id), jti=str(uuid4()))
    stored = service.store_refresh_token(user.id, refresh_token)

    with session_factory() as session:
        db_token = session.get(RefreshToken, stored.id)
        assert db_token is not None
        db_token.expires_at = _utcnow() - timedelta(seconds=1)
        session.commit()

    with pytest.raises(HTTPException) as exc_info:
        service.rotate_refresh_token(refresh_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "refresh_expired"

    with session_factory() as session:
        remaining = (
            session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
            .scalars()
            .all()
        )
        assert remaining == []


def test_get_current_user_rejects_expired_session(
    service: UserService, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_time = datetime.now(UTC)
    times = iter([base_time, base_time + timedelta(seconds=1)])

    monkeypatch.setattr(
        "backend.core.security._now",
        lambda: next(times),
    )
    user = service.create_user("expired-session@example.com", "secret")
    active_token, active_session = service.create_session(user.id)
    expired_token, expired_session = service.create_session(user.id)

    with session_factory() as session:
        stored = session.get(SessionModel, expired_session.id)
        assert stored is not None
        stored.expires_at = _utcnow() - timedelta(minutes=1)
        session.commit()

    active_sessions = service.get_active_sessions(user.id)
    assert {sess.id for sess in active_sessions} == {active_session.id}

    with pytest.raises(InvalidTokenError):
        service.get_current_user(expired_token)

    current_user = service.get_current_user(active_token)
    assert current_user.id == user.id


def test_logout_revoke_all_clears_refresh_tokens(
    service: UserService, session_factory
) -> None:
    user = service.create_user("logout-db@example.com", "secret")
    first_token = create_refresh_token(sub=str(user.id), jti=str(uuid4()))
    second_token = create_refresh_token(sub=str(user.id), jti=str(uuid4()))
    service.store_refresh_token(user.id, first_token)
    service.store_refresh_token(user.id, second_token)

    with session_factory() as session:
        request = LogoutRequest(refresh_token=first_token, revoke_all=True)
        response = logout(request, db=session)
        assert response == {"detail": "All sessions revoked"}

        remaining = (
            session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
            .scalars()
            .all()
        )
        assert remaining == []

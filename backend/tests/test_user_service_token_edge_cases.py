from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core import security as security_module
from backend.models import Base, RefreshToken, Session
from backend.services import user_service as user_service_module
from backend.services.user_service import InvalidTokenError, UserService


@pytest.fixture()
def session_factory() -> Generator[sessionmaker, None, None]:
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


def _encode_token(payload: dict[str, object]) -> str:
    return jwt.encode(payload, security_module.ACCESS_SECRET, algorithm=security_module.JWT_ALG)


def test_extract_identity_validates_uuid(service: UserService) -> None:
    with pytest.raises(InvalidTokenError):
        UserService._extract_identity({})

    with pytest.raises(InvalidTokenError):
        UserService._extract_identity({"user_id": "not-a-uuid"})

    sample_id = uuid4()
    user_id, email = UserService._extract_identity({"user_id": str(sample_id), "email": "user@example.com"})
    assert user_id == sample_id
    assert email == "user@example.com"


def test_create_session_rejects_token_from_other_user(service: UserService) -> None:
    owner = service.create_user("owner@example.com", "secret")
    stranger = service.create_user("intruder@example.com", "secret")

    foreign_token, _ = service.create_session(stranger.id)

    with pytest.raises(InvalidTokenError):
        service.create_session(owner.id, token=foreign_token)


def test_create_session_rejects_token_with_mismatched_email(service: UserService) -> None:
    user = service.create_user("user@example.com", "secret")
    payload = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "email": "another@example.com",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    forged_token = _encode_token(payload)

    with pytest.raises(InvalidTokenError):
        service.create_session(user.id, token=forged_token)


def test_create_session_with_valid_token_reuses_payload(
    service: UserService, session_factory
) -> None:
    user = service.create_user("reuse@example.com", "secret")
    token, session_obj = service.create_session(user.id)

    with session_factory() as session:
        stored = session.get(Session, session_obj.id)
        assert stored is not None
        session.delete(stored)
        session.commit()

    reused_token, reused_session = service.create_session(user.id, token=token)

    assert reused_token == token
    assert reused_session.user_id == user.id
    assert reused_session.token == session_obj.token


def test_store_refresh_token_accepts_invalid_payload(service: UserService, session_factory) -> None:
    user = service.create_user("refresh@example.com", "secret")
    stored = service.store_refresh_token(user.id, "not-a-jwt-token")

    assert stored.user_id == user.id
    assert getattr(stored, "expires_at", None) in {None, stored.expires_at}

    with session_factory() as session:
        db_token = session.get(RefreshToken, stored.id)
        assert db_token is not None
        assert db_token.token == "not-a-jwt-token"


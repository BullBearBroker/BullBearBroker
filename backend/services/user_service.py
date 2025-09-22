from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession, sessionmaker, selectinload

from models import Alert, Session as SessionModel, User
from utils.config import password_context

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL debe estar configurada")
if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("DATABASE_URL debe apuntar a una base de datos PostgreSQL")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class UserAlreadyExistsError(Exception):
    """Se lanza cuando se intenta crear un usuario ya registrado."""


class UserNotFoundError(Exception):
    """Se lanza cuando el usuario no existe en la base de datos."""


class InvalidCredentialsError(Exception):
    """Se lanza cuando las credenciales proporcionadas no son válidas."""


class UserService:
    def __init__(self, session_factory: sessionmaker = SessionLocal):
        self._session_factory = session_factory

    @contextmanager
    def _session_scope(self) -> Iterable[OrmSession]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _detach_entity(session: OrmSession, entity):
        session.flush()
        session.refresh(entity)
        session.expunge(entity)
        return entity

    def _user_with_relationships(self, session: OrmSession, user: User) -> User:
        session.refresh(
            user,
            attribute_names=["alerts", "sessions"],
        )
        for collection in (user.alerts, user.sessions):
            for item in collection:
                session.expunge(item)
        return self._detach_entity(session, user)

    def create_user(self, email: str, password: str) -> User:
        hashed_password = password_context.hash(password)
        with self._session_scope() as session:
            if session.query(User).filter(User.email == email).first():
                raise UserAlreadyExistsError("Email ya está registrado")

            user = User(
                email=email,
                password_hash=hashed_password,
            )
            session.add(user)
            return self._user_with_relationships(session, user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self._session_scope() as session:
            user = (
                session.query(User)
                .options(selectinload(User.alerts), selectinload(User.sessions))
                .filter(User.email == email)
                .first()
            )
            if not user:
                return None
            session.expunge(user)
            for collection in (user.alerts, user.sessions):
                for item in collection:
                    session.expunge(item)
            return user

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise InvalidCredentialsError("Credenciales inválidas")
        return user

    def create_session(
        self, user_id: UUID, token: str, expires_in: timedelta | None = None
    ) -> SessionModel:
        expires_at: datetime | None = None
        if expires_in is not None:
            expires_at = datetime.utcnow() + expires_in

        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise UserNotFoundError("Usuario no encontrado")

            session_obj = SessionModel(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
            )
            session.add(session_obj)
            return self._detach_entity(session, session_obj)

    def get_active_sessions(self, user_id: UUID) -> list[SessionModel]:
        with self._session_scope() as session:
            now = datetime.utcnow()
            sessions = (
                session.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    (SessionModel.expires_at.is_(None))
                    | (SessionModel.expires_at > now),
                )
                .all()
            )
            for sess in sessions:
                session.expunge(sess)
            return sessions

    def register_session_activity(self, token: str) -> None:
        # La tabla de sesiones ya no registra actividad adicional; se mantiene para compatibilidad.
        return None

    def create_alert(
        self,
        user_id: UUID,
        *,
        asset: str,
        value: float,
        condition: str = "above",
    ) -> Alert:
        with self._session_scope() as session:
            if not session.get(User, user_id):
                raise UserNotFoundError("Usuario no encontrado")

            alert = Alert(
                user_id=user_id,
                asset=asset.upper(),
                value=value,
                condition=condition,
            )
            session.add(alert)
            return self._detach_entity(session, alert)

    def get_alerts_for_user(self, user_id: UUID) -> list[Alert]:
        with self._session_scope() as session:
            alerts = session.query(Alert).filter(Alert.user_id == user_id).all()
            for alert in alerts:
                session.expunge(alert)
            return alerts


user_service = UserService()

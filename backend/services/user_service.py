from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, User
from utils.config import password_context

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bullbearbroker.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base.metadata.create_all(bind=engine)


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
    def _session_scope(self) -> Session:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _detach_user(self, session: Session, user: User) -> User:
        session.flush()
        session.refresh(user)
        session.expunge(user)
        return user

    def create_user(self, email: str, username: str, password: str) -> User:
        hashed_password = password_context.hash(password)
        with self._session_scope() as session:
            if session.query(User).filter(User.email == email).first():
                raise UserAlreadyExistsError("Email ya está registrado")

            user = User(
                email=email,
                username=username,
                hashed_password=hashed_password,
            )
            session.add(user)
            return self._detach_user(session, user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self._session_scope() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                return None
            return self._detach_user(session, user)

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise InvalidCredentialsError("Credenciales inválidas")
        return user

    def increment_api_usage(self, email: str) -> User:
        with self._session_scope() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                raise UserNotFoundError("Usuario no encontrado")

            user.reset_api_counter()
            user.api_calls_today += 1
            return self._detach_user(session, user)


user_service = UserService()

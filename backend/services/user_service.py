from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Alert, Base, User, UserSession
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


class SessionNotFoundError(Exception):
    """Se lanza cuando no se encuentra una sesión activa."""


class AlertNotFoundError(Exception):
    """Se lanza cuando no existe una alerta solicitada."""


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

    def _detach(self, session: Session, instance):
        session.flush()
        session.refresh(instance)
        session.expunge(instance)
        return instance

    def _detach_list(self, session: Session, instances: Iterable):
        detached = []
        for instance in instances:
            session.flush()
            session.refresh(instance)
            session.expunge(instance)
            detached.append(instance)
        return detached

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
            return self._detach(session, user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self._session_scope() as session:
            user = session.query(User).filter(User.email == email).first()
            if not user:
                return None
            return self._detach(session, user)

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                return None
            return self._detach(session, user)

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
            return self._detach(session, user)

    # --- Gestión de sesiones ---
    def create_session(
        self,
        user_id: int,
        token: str,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        with self._session_scope() as session:
            session_obj = UserSession(
                user_id=user_id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(session_obj)
            return self._detach(session, session_obj)

    def get_active_session(self, token: str) -> Optional[UserSession]:
        with self._session_scope() as session:
            session_obj = (
                session.query(UserSession)
                .filter(UserSession.token == token, UserSession.active.is_(True))
                .first()
            )
            if not session_obj:
                return None
            return self._detach(session, session_obj)

    def invalidate_session(self, token: str) -> None:
        with self._session_scope() as session:
            session_obj = (
                session.query(UserSession)
                .filter(UserSession.token == token, UserSession.active.is_(True))
                .first()
            )
            if not session_obj:
                raise SessionNotFoundError("Sesión no encontrada")
            session_obj.active = False

    def purge_expired_sessions(self, reference: Optional[datetime] = None) -> int:
        reference = reference or datetime.utcnow()
        with self._session_scope() as session:
            expired_sessions = (
                session.query(UserSession)
                .filter(
                    UserSession.expires_at.isnot(None),
                    UserSession.expires_at < reference,
                    UserSession.active.is_(True),
                )
                .all()
            )
            count = 0
            for session_obj in expired_sessions:
                session_obj.active = False
                count += 1
            return count

    # --- Gestión de alertas ---
    def create_alert(
        self,
        user_id: int,
        symbol: str,
        condition_type: str,
        threshold_value: float,
        asset_type: Optional[str] = None,
        note: Optional[str] = None,
        is_repeating: bool = False,
    ) -> Alert:
        with self._session_scope() as session:
            alert = Alert(
                user_id=user_id,
                symbol=symbol.upper(),
                asset_type=asset_type,
                condition_type=condition_type,
                threshold_value=threshold_value,
                note=note,
                is_repeating=is_repeating,
            )
            session.add(alert)
            return self._detach(session, alert)

    def get_alerts_for_user(self, user_id: int, active_only: bool = False) -> List[Alert]:
        with self._session_scope() as session:
            query = session.query(Alert).filter(Alert.user_id == user_id)
            if active_only:
                query = query.filter(Alert.active.is_(True))
            alerts = query.order_by(Alert.created_at.desc()).all()
            return self._detach_list(session, alerts)

    def deactivate_alert(self, alert_id: int, user_id: Optional[int] = None) -> Alert:
        with self._session_scope() as session:
            alert = session.get(Alert, alert_id)
            if not alert:
                raise AlertNotFoundError("Alerta no encontrada")
            if user_id is not None and alert.user_id != user_id:
                raise AlertNotFoundError("Alerta no encontrada para el usuario")
            alert.active = False
            return self._detach(session, alert)

    def get_all_active_alerts(self) -> List[Alert]:
        with self._session_scope() as session:
            alerts = session.query(Alert).filter(Alert.active.is_(True)).all()
            return self._detach_list(session, alerts)

    def mark_alert_triggered(
        self, alert_id: int, triggered_price: float, triggered_at: Optional[datetime] = None
    ) -> Optional[Alert]:
        with self._session_scope() as session:
            alert = session.get(Alert, alert_id)
            if not alert:
                return None
            alert.triggered_at = triggered_at or datetime.utcnow()
            alert.last_triggered_price = triggered_price
            if not alert.is_repeating:
                alert.active = False
            return self._detach(session, alert)


user_service = UserService()

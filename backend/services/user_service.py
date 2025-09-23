from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional, Tuple
from uuid import UUID

import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession, sessionmaker, selectinload

from backend.models import Alert, Session as SessionModel, User
from backend.utils.config import Config, password_context

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


DEFAULT_SESSION_TTL = timedelta(hours=24)


class InvalidTokenError(Exception):
    """Se lanza cuando el token JWT es inválido o expiró."""


class UserService:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        *,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        default_session_ttl: timedelta = DEFAULT_SESSION_TTL,
    ):
        self._session_factory = session_factory
        self._jwt_secret_key = secret_key or Config.JWT_SECRET_KEY
        self._jwt_algorithm = algorithm or Config.JWT_ALGORITHM
        self._default_session_ttl = default_session_ttl

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
            session.add(user)       # ✅ se añade a la sesión
            session.flush()         # ✅ se asegura de generar el ID
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
            session.expunge(user)   # ✅ suficiente
            return user

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise InvalidCredentialsError("Credenciales inválidas")
        return user

    def _build_token_payload(self, user: User, expires_at: datetime) -> dict[str, Any]:
        now = datetime.utcnow()
        return {
            "sub": str(user.id),
            "user_id": str(user.id),
            "email": user.email,
            "iat": now,
            "nbf": now,
            "exp": expires_at,
        }

    def _compute_expiration(self, expires_in: Optional[timedelta]) -> datetime:
        delta = expires_in or self._default_session_ttl
        return datetime.utcnow() + delta

    def _encode_token(self, payload: dict[str, Any]) -> str:
        return jwt.encode(payload, self._jwt_secret_key, algorithm=self._jwt_algorithm)

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self._jwt_secret_key, algorithms=[self._jwt_algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("Token expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("Token inválido") from exc

    @staticmethod
    def _extract_expiration(payload: dict[str, Any]) -> datetime:
        exp = payload.get("exp")
        if isinstance(exp, datetime):
            return exp
        if isinstance(exp, (int, float)):
            return datetime.utcfromtimestamp(exp)
        raise InvalidTokenError("Token inválido: expiración ausente")

    @staticmethod
    def _extract_identity(payload: dict[str, Any]) -> Tuple[UUID, str]:
        raw_user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")
        if not raw_user_id or not email:
            raise InvalidTokenError("Token inválido")
        try:
            return UUID(str(raw_user_id)), str(email)
        except ValueError as exc:
            raise InvalidTokenError("Token inválido") from exc

    def create_access_token(
        self, user: User, expires_in: Optional[timedelta] = None
    ) -> Tuple[str, datetime]:
        expires_at = self._compute_expiration(expires_in)
        payload = self._build_token_payload(user, expires_at)
        token = self._encode_token(payload)
        return token, expires_at

    def create_session(
        self,
        user_id: UUID,
        token: Optional[str] = None,
        expires_in: timedelta | None = None,
    ) -> Tuple[str, SessionModel]:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise UserNotFoundError("Usuario no encontrado")

            if token is None:
                token, expires_at = self.create_access_token(user, expires_in)
            else:
                payload = self._decode_token(token)
                token_user_id, token_email = self._extract_identity(payload)
                if token_user_id != user.id or token_email != user.email:
                    raise InvalidTokenError("Token inválido para el usuario especificado")
                expires_at = self._extract_expiration(payload)

            session_obj = SessionModel(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
            )
            session.add(session_obj)
            return token, self._detach_entity(session, session_obj)

    def get_active_sessions(self, user_id: UUID) -> list[SessionModel]:
        with self._session_scope() as session:
            now = datetime.utcnow()
            sessions = (
                session.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.expires_at > now,
                )
                .all()
            )
            for sess in sessions:
                session.expunge(sess)
            return sessions

    def get_current_user(self, token: str) -> User:
        payload = self._decode_token(token)
        user_id, email = self._extract_identity(payload)

        with self._session_scope() as session:
            session_record = (
                session.query(SessionModel)
                .filter(
                    SessionModel.token == token,
                    SessionModel.user_id == user_id,
                    SessionModel.expires_at > datetime.utcnow(),
                )
                .order_by(SessionModel.expires_at.desc())
                .first()
            )
            if not session_record:
                raise InvalidTokenError("Token inválido")

            user = session.get(User, user_id)
            if not user or user.email != email:
                raise InvalidTokenError("Token inválido")

            return self._user_with_relationships(session, user)

    def register_session_activity(self, token: str) -> None:
        # La tabla de sesiones ya no registra actividad adicional; se mantiene para compatibilidad.
        return None

    def create_alert(
        self,
        user_id: UUID,
        *,
        asset: str,
        value: float,
        condition: str = ">",
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

    def delete_alert_for_user(self, user_id: UUID, alert_id: UUID) -> bool:
        """Eliminar una alerta de un usuario. Devuelve True si se borró, False si no existía."""
        with self._session_scope() as session:
            alert = (
                session.query(Alert)
                .filter(Alert.id == alert_id, Alert.user_id == user_id)
                .first()
            )
            if not alert:
                return False
            session.delete(alert)
            return True

    def update_alert(
        self,
        user_id: UUID,
        alert_id: UUID,
        *,
        asset: Optional[str] = None,
        value: Optional[float] = None,
        condition: Optional[str] = None,
    ) -> Alert:
        """Actualizar los campos de una alerta existente."""
        with self._session_scope() as session:
            alert = (
                session.query(Alert)
                .filter(Alert.id == alert_id, Alert.user_id == user_id)
                .first()
            )
            if not alert:
                raise UserNotFoundError("Alerta no encontrada para este usuario")

            if asset is not None:
                alert.asset = asset.upper()
            if value is not None:
                alert.value = value
            if condition is not None:
                alert.condition = condition

            alert.updated_at = datetime.utcnow()
            session.add(alert)
            return self._detach_entity(session, alert)

    def delete_all_alerts_for_user(self, user_id: UUID) -> int:
        """Eliminar todas las alertas de un usuario. Devuelve el número de alertas borradas."""
        with self._session_scope() as session:
            deleted = session.query(Alert).filter(Alert.user_id == user_id).delete()
            return deleted


user_service = UserService()

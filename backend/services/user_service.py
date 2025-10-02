from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload, sessionmaker

from backend.core.logging_config import log_event
from backend.core.security import create_access_token as core_create_access_token
from backend.core.security import create_refresh_token as core_create_refresh_token
from backend.core.security import (
    decode_access,
    decode_refresh,
)
from backend.database import SessionLocal
from backend.models import Alert, User
from backend.models import Session as SessionModel
from backend.models.refresh_token import RefreshToken
from backend.models.user import RiskProfile  # [Codex] nuevo
from backend.utils.config import Config, password_context

LOGGER = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    """Se lanza cuando se intenta crear un usuario ya registrado."""


class UserNotFoundError(Exception):
    """Se lanza cuando el usuario no existe en la base de datos."""


class InvalidCredentialsError(Exception):
    """Se lanza cuando las credenciales proporcionadas no son válidas."""


ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)

DEFAULT_SESSION_TTL = ACCESS_TOKEN_TTL


class InvalidTokenError(Exception):
    """Se lanza cuando el token JWT es inválido o expiró."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class UserService:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        *,
        secret_key: str | None = None,
        algorithm: str | None = None,
        default_session_ttl: timedelta = DEFAULT_SESSION_TTL,
    ):
        self._session_factory = session_factory
        self._jwt_secret_key = secret_key or Config.JWT_SECRET_KEY
        self._jwt_algorithm = algorithm or Config.JWT_ALGORITHM
        self._default_session_ttl = default_session_ttl
        self._in_memory_refresh_tokens: dict[str, SimpleNamespace] = {}

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
            attribute_names=["alerts", "sessions", "refresh_tokens"],
        )
        return self._detach_entity(session, user)

    def create_user(self, email: str, password: str, *, risk_profile: str | None = None) -> User:
        hashed_password = password_context.hash(password)
        normalized_profile: str | None = None
        if risk_profile:
            candidate = risk_profile.lower()
            valid_values = {item.value for item in RiskProfile}
            if candidate not in valid_values:
                raise ValueError("Perfil de riesgo inválido")
            normalized_profile = candidate
        with self._session_scope() as session:
            if session.query(User).filter(User.email == email).first():
                raise UserAlreadyExistsError("Email ya está registrado")

            user = User(
                email=email,
                password_hash=hashed_password,
                risk_profile=normalized_profile,  # [Codex] nuevo
            )
            session.add(user)       # ✅ se añade a la sesión
            session.flush()         # ✅ se asegura de generar el ID
            return self._user_with_relationships(session, user)

    def ensure_user(self, email: str, password: str) -> User:
        """Garantiza que exista un usuario con las credenciales indicadas."""

        hashed_password = password_context.hash(password)
        with self._session_scope() as session:
            user = (
                session.query(User)
                .options(selectinload(User.alerts), selectinload(User.sessions))
                .filter(User.email == email)
                .first()
            )
            if user:
                return self._user_with_relationships(session, user)

            user = User(email=email, password_hash=hashed_password)
            session.add(user)
            session.flush()
            return self._user_with_relationships(session, user)

    def get_user_by_email(self, email: str) -> User | None:
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

    def _compute_expiration(self, expires_in: timedelta | None) -> datetime:
        delta = expires_in or self._default_session_ttl
        return _utcnow() + delta

    def _encode_token(self, payload: dict[str, Any]) -> str:
        return jwt.encode(payload, self._jwt_secret_key, algorithm=self._jwt_algorithm)

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            return decode_access(token)
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("Token expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("Token inválido") from exc

    @staticmethod
    def _extract_expiration(payload: dict[str, Any]) -> datetime:
        exp = payload.get("exp")
        if isinstance(exp, datetime):
            return exp
        if isinstance(exp, int | float):
            return datetime.utcfromtimestamp(exp)
        raise InvalidTokenError("Token inválido: expiración ausente")

    @staticmethod
    def _extract_identity(payload: dict[str, Any]) -> tuple[UUID, str | None]:
        raw_user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")  # puede venir o no
        if not raw_user_id:
            raise InvalidTokenError("Token inválido")
        try:
            return UUID(str(raw_user_id)), (str(email) if email is not None else None)
        except ValueError as exc:
            raise InvalidTokenError("Token inválido") from exc

    def create_access_token(
        self, user: User, expires_in: timedelta | None = None
    ) -> tuple[str, datetime]:
        expires_in = expires_in or ACCESS_TOKEN_TTL
        expires_at = _utcnow() + expires_in
        token = core_create_access_token(sub=str(user.id), extra={"user_id": str(user.id)})
        return token, expires_at

    def create_session(
        self,
        user_id: UUID,
        token: str | None = None,
        expires_in: timedelta | None = None,
    ) -> tuple[str, SessionModel]:
        with self._session_scope() as session:
            user = session.get(User, user_id)
            if not user:
                raise UserNotFoundError("Usuario no encontrado")

            if token is None:
                token, expires_at = self.create_access_token(user, expires_in)
            else:
                payload = self._decode_token(token)
                token_user_id, token_email = self._extract_identity(payload)
                if token_user_id != user.id or (
                    token_email is not None and token_email != user.email
                ):
                    raise InvalidTokenError("Token inválido para el usuario especificado")
                extracted_exp = self._extract_expiration(payload)
                expires_at = _as_aware_utc(extracted_exp) or extracted_exp

            session_obj = SessionModel(
                user_id=user.id,
                token=token,
                expires_at=_as_aware_utc(expires_at) or expires_at,
            )
            session.add(session_obj)
            return token, self._detach_entity(session, session_obj)

    def create_refresh_token(
        self,
        user_id: UUID,
        expires_in: timedelta | None = None,
    ) -> tuple[str, datetime]:
        expires_in = expires_in or REFRESH_TOKEN_TTL
        expires_at = _utcnow() + expires_in
        token_value = core_create_refresh_token(sub=str(user_id))
        self._in_memory_refresh_tokens[token_value] = SimpleNamespace(
            user_id=user_id,
            expires_at=expires_at,
        )
        return token_value, expires_at

    def get_active_sessions(self, user_id: UUID) -> list[SessionModel]:
        with self._session_scope() as session:
            now = _utcnow()
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
                    SessionModel.expires_at > _utcnow(),
                )
                .order_by(SessionModel.expires_at.desc())
                .first()
            )
            if not session_record:
                raise InvalidTokenError("Token inválido")

            user = session.get(User, user_id)
            if not user or (email is not None and user.email != email):
                raise InvalidTokenError("Token inválido")

            return self._user_with_relationships(session, user)

    def revoke_refresh_token(self, token: str) -> None:
        self._in_memory_refresh_tokens.pop(token, None)

    def rotate_refresh_token(self, token_str: str) -> tuple[User, str, datetime]:
        """Rota un refresh token utilizando almacenamiento en base de datos."""

        payload = decode_refresh(token_str)
        user_id = UUID(payload["sub"])
        now = _utcnow()

        with SessionLocal() as db:
            stored: RefreshToken | None = db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.token == token_str,
                )
            ).scalars().first()

            if not stored:
                raise HTTPException(status_code=401, detail="invalid_refresh")

            expires_attr = getattr(stored, "expires_at", None)
            aware_exp = _as_aware_utc(expires_attr)
            if aware_exp is not None and aware_exp <= now:
                db.delete(stored)
                db.commit()
                raise HTTPException(status_code=401, detail="refresh_expired")

            db.delete(stored)

            new_refresh = core_create_refresh_token(sub=str(user_id))
            db.add(
                RefreshToken(
                    id=uuid4(),
                    user_id=user_id,
                    token=new_refresh,
                )
            )
            db.commit()

            new_payload = decode_refresh(new_refresh)
            refresh_expires = datetime.fromtimestamp(
                int(new_payload["exp"]), tz=UTC
            )

            user = db.get(User, user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="invalid_refresh")

        with self._session_scope() as session:
            fresh_user = session.get(User, user_id)
            if not fresh_user:
                raise HTTPException(status_code=401, detail="invalid_refresh")
            hydrated_user = self._user_with_relationships(session, fresh_user)
            return hydrated_user, new_refresh, refresh_expires

    def issue_token_pair(
        self, user: User
    ) -> tuple[str, datetime, str, datetime]:
        access_token, session = self.create_session(
            user_id=user.id,
            expires_in=ACCESS_TOKEN_TTL,
        )
        refresh_token, refresh_expires_at = self.create_refresh_token(
            user_id=user.id,
            expires_in=REFRESH_TOKEN_TTL,
        )
        return access_token, session.expires_at, refresh_token, refresh_expires_at

    def store_refresh_token(self, user_id: UUID, token: str) -> RefreshToken:
        """
        Persiste un refresh token en la tabla refresh_tokens.
        Si el modelo tiene columna 'expires_at', se completa; si no, se omite.
        """
        expires_dt = None
        try:
            payload = decode_refresh(token)  # valida firma y decodifica JWT
            exp = int(payload["exp"])
            expires_dt = datetime.fromtimestamp(exp, tz=UTC)
        except Exception:
            # No bloquear guardado si no pudimos decodificar por alguna razón
            expires_dt = None

        with SessionLocal() as db:
            data = {
                "id": uuid4(),
                "user_id": user_id,
                "token": token,
            }
            # Solo setea expires_at si la columna existe en el modelo
            if hasattr(RefreshToken, "expires_at") and expires_dt is not None:
                data["expires_at"] = expires_dt

            db_ref = RefreshToken(**data)
            db.add(db_ref)
            db.commit()
            db.refresh(db_ref)
            return db_ref

    def revoke_all_refresh_tokens(self, user_id: UUID) -> None:
        to_remove = [
            token
            for token, data in self._in_memory_refresh_tokens.items()
            if data.user_id == user_id
        ]
        for token in to_remove:
            self._in_memory_refresh_tokens.pop(token, None)

    def register_session_activity(self, token: str) -> None:
        # La tabla de sesiones ya no registra actividad adicional; se mantiene para compatibilidad.
        return None

    def register_external_session(
        self, user_id: UUID, access_token: str, access_expires: datetime
    ) -> SessionModel:
        """Persiste una sesión de acceso en la tabla 'sessions'."""

        with SessionLocal() as db:
            max_sessions = getattr(Config, "MAX_CONCURRENT_SESSIONS", 0)
            if max_sessions and max_sessions > 0:
                now = _utcnow()
                active_sessions = (
                    db.query(SessionModel)
                    .filter(
                        SessionModel.user_id == user_id,
                        SessionModel.expires_at > now,
                    )
                    .order_by(SessionModel.created_at.asc())
                    .all()
                )
                if len(active_sessions) >= max_sessions:
                    evicted_session = active_sessions[0]
                    db.delete(evicted_session)
                    db.flush()
                    user_hash = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[
                        :8
                    ]
                    log_event(
                        LOGGER,
                        service="user_service",
                        event="session_evicted",
                        level="info",
                        user_id_hash=user_hash,
                        session_id=str(getattr(evicted_session, "id", "")),
                    )
            db_sess = SessionModel(
                id=uuid4(),
                user_id=user_id,
                token=access_token,
                expires_at=_as_aware_utc(access_expires) or access_expires,
            )
            db.add(db_sess)
            db.commit()
            db.refresh(db_sess)
            return db_sess

    def create_alert(
        self,
        user_id: UUID,
        *,
        title: str,
        asset: str,
        value: float | None = None,
        condition: str = ">",
        active: bool = True,
    ) -> Alert:
        with self._session_scope() as session:
            if not session.get(User, user_id):
                raise UserNotFoundError("Usuario no encontrado")

            title_clean = (title or "").strip()
            if not title_clean:
                raise ValueError("El título de la alerta es obligatorio")

            asset_clean = (asset or "").strip().upper()
            if not asset_clean:
                raise ValueError("El activo de la alerta es obligatorio")

            condition_clean = (condition or "").strip() or ">"

            alert = Alert(
                user_id=user_id,
                title=title_clean,
                asset=asset_clean,
                value=float(value if value is not None else 0.0),
                condition=condition_clean,
                active=bool(active),
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
        title: str | None = None,
        asset: str | None = None,
        value: float | None = None,
        condition: str | None = None,
        active: bool | None = None,
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

            if title is not None:
                title_clean = title.strip()
                if not title_clean:
                    raise ValueError("El título de la alerta es obligatorio")
                alert.title = title_clean
            if asset is not None:
                asset_clean = asset.strip().upper()
                if not asset_clean:
                    raise ValueError("El activo de la alerta es obligatorio")
                alert.asset = asset_clean
            if value is not None:
                alert.value = float(value)
            if condition is not None:
                cleaned_condition = condition.strip()
                if not cleaned_condition:
                    raise ValueError("La condición de la alerta no puede estar vacía")
                alert.condition = cleaned_condition
            if active is not None:
                alert.active = bool(active)

            alert.updated_at = datetime.utcnow()
            session.add(alert)
            return self._detach_entity(session, alert)

    def delete_all_alerts_for_user(self, user_id: UUID) -> int:
        """Eliminar todas las alertas de un usuario. Devuelve el número de alertas borradas."""
        with self._session_scope() as session:
            deleted = session.query(Alert).filter(Alert.user_id == user_id).delete()
            return deleted


user_service = UserService()

try:
    default_email = os.getenv("BULLBEAR_DEFAULT_USER", "test@bullbear.ai")
    default_password = os.getenv("BULLBEAR_DEFAULT_PASSWORD", "Test1234!")
    user_service.ensure_user(default_email, default_password)
    logging.getLogger(__name__).info("Usuario por defecto disponible (%s)", default_email)
except Exception as exc:  # pragma: no cover - útil en despliegues sin DB
    logging.getLogger(__name__).warning("No se pudo garantizar usuario por defecto: %s", exc)

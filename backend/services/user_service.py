from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.session import SessionLocal
from models import User
from utils.config import password_context


class UserAlreadyExistsError(Exception):
    """Se lanza cuando se intenta crear un usuario ya registrado."""


class UserNotFoundError(Exception):
    """Se lanza cuando el usuario no existe en la base de datos."""


class InvalidCredentialsError(Exception):
    """Se lanza cuando las credenciales proporcionadas no son válidas."""


class UserService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = SessionLocal):
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _detach_user(self, session: AsyncSession, user: User) -> User:
        await session.flush()
        await session.refresh(user)
        session.expunge(user)
        return user

    async def create_user(self, email: str, username: str, password: str) -> User:
        hashed_password = password_context.hash(password)
        async with self._session_scope() as session:
            result = await session.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise UserAlreadyExistsError("Email ya está registrado")

            user = User(
                email=email,
                username=username,
                hashed_password=hashed_password,
            )
            session.add(user)
            return await self._detach_user(session, user)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self._session_scope() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                return None
            return await self._detach_user(session, user)

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise InvalidCredentialsError("Credenciales inválidas")
        return user

    async def increment_api_usage(self, email: str) -> User:
        async with self._session_scope() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                raise UserNotFoundError("Usuario no encontrado")

            user.reset_api_counter()
            user.api_calls_today += 1
            return await self._detach_user(session, user)


user_service = UserService()

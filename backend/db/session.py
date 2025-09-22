from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/bullbearbroker"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError(
        "DATABASE_URL debe utilizar el driver de PostgreSQL (por ejemplo postgresql+asyncpg).",
    )

try:
    engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False, future=True)
except ModuleNotFoundError as exc:
    raise RuntimeError("Se requiere instalar asyncpg para usar la base de datos PostgreSQL.") from exc

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Contexto de sesión con manejo de commit/rollback automático."""

    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia para FastAPI que entrega una sesión asincrónica."""

    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

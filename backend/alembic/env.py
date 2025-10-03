from __future__ import annotations

import os
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from backend import (  # noqa: F401  (asegura que se importen los modelos)
    models as _models,
)

# 🚩 Importa la Base y registra todos los modelos en la metadata
from backend.models import Base

# Alembic Config object
config = context.config

# Logging de Alembic (opcional)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Carga variables de entorno desde .env en la raíz
load_dotenv()

# Obtiene la URL de la DB desde el entorno o desde alembic.ini como fallback
database_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not database_url:
    raise RuntimeError("DATABASE_URL debe estar configurada para ejecutar migraciones")

# Inyecta la URL en la config activa (para offline y online)
config.set_main_option("sqlalchemy.url", database_url)

# Metadata objetivo para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo 'offline' (sin conectar).
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        version_table_pk_type=sa.String(64),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo 'online' (con conexión a la DB).
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            version_table_pk_type=sa.String(64),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

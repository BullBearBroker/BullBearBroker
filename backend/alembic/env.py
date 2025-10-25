from __future__ import annotations

import logging
import os
from logging.config import fileConfig
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import sqlalchemy as sa
from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# 🚩 Importa la Base y registra todos los modelos en la metadata
from backend.models import Base
from backend.utils.config import get_database_url

# Alembic Config object
config = context.config
logger = logging.getLogger("alembic.env")

# Logging de Alembic (opcional)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Carga variables de entorno desde .env en la raíz
load_dotenv()

# Obtiene la URL de la DB desde el entorno o desde alembic.ini como fallback
db_use_pool = os.getenv("DB_USE_POOL", "false").lower() == "true"
database_url = get_database_url()
hostaddr_override = os.getenv("SUPABASE_DB_HOSTADDR")

if not database_url:
    raise RuntimeError(
        "SUPABASE_DB_URL debe estar configurada para ejecutar migraciones"
    )

if not db_use_pool:
    if hostaddr_override and "hostaddr=" not in database_url:
        parsed_override = urlparse(database_url)
        query_items_override = dict(
            parse_qsl(parsed_override.query, keep_blank_values=True)
        )
        query_items_override["hostaddr"] = hostaddr_override
        database_url = urlunparse(
            parsed_override._replace(query=urlencode(query_items_override))
        )
        logger.info(
            "# QA: alembic using direct URL (env hostaddr override)",
            extra={"ipv4_forced": True},
        )
    parsed = urlparse(database_url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ipv4_forced = "hostaddr" in query_items
    logger.info("# QA: alembic using direct URL", extra={"ipv4_forced": ipv4_forced})
else:
    logger.info("alembic using pooler URL")

# Inyecta la URL en la config activa (para offline y online)
config.set_main_option("sqlalchemy.url", database_url)

if database_url.startswith("sqlite"):
    from sqlalchemy.dialects.postgresql import UUID as PGUUID
    from sqlalchemy.dialects.sqlite import base as sqlite_base

    sqlite_base.dialect.colspecs[PGUUID] = sa.types.String

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

    connect_args: dict[str, object] = {}
    url = configuration["sqlalchemy.url"]
    if url and not url.startswith("sqlite") and not db_use_pool:
        connect_args["prepared_statement_cache_size"] = 0
    configuration["sqlalchemy.connect_args"] = connect_args

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

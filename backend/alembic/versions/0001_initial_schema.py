"""initial schema"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    uuid_server_default = sa.text("gen_random_uuid()") if is_postgres else None
    timestamp_default = sa.func.now() if is_postgres else sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=uuid_server_default,
            primary_key=True,
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=timestamp_default, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=timestamp_default, nullable=False
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=uuid_server_default,
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset", sa.String(length=50), nullable=False),
        sa.Column(
            "condition",
            sa.String(length=20),
            server_default=sa.text("'>'"),
            nullable=False,
        ),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=timestamp_default, nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=timestamp_default, nullable=False
        ),
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=uuid_server_default,
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

"""correct schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_correct_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", new_column_name="password_hash")
    op.drop_column("users", "username")
    op.drop_column("users", "subscription_level")
    op.drop_column("users", "api_calls_today")
    op.drop_column("users", "last_reset")
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.alter_column("alerts", "symbol", new_column_name="asset")
    op.alter_column("alerts", "comparison", new_column_name="condition")
    op.alter_column("alerts", "target_price", new_column_name="value")
    op.drop_column("alerts", "channel")
    op.drop_column("alerts", "message")
    op.drop_column("alerts", "acknowledged_at")
    op.add_column(
        "alerts",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.drop_column("sessions", "last_seen_at")
    op.drop_column("sessions", "revoked_at")


def downgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )

    op.drop_column("alerts", "updated_at")
    op.add_column(
        "alerts",
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("message", sa.String(), nullable=False),
    )
    op.add_column(
        "alerts",
        sa.Column("channel", sa.String(length=50), nullable=False),
    )
    op.alter_column("alerts", "value", new_column_name="target_price")
    op.alter_column("alerts", "condition", new_column_name="comparison")
    op.alter_column("alerts", "asset", new_column_name="symbol")

    op.drop_column("users", "updated_at")
    op.add_column(
        "users",
        sa.Column("last_reset", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("api_calls_today", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("subscription_level", sa.String(), server_default="free", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("username", sa.String(), nullable=False),
    )
    op.alter_column("users", "password_hash", new_column_name="hashed_password")

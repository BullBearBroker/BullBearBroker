"""make session expires_at not nullable"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_session_expires_not_null"
down_revision = "0002_add_updated_at_to_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sessions
            SET expires_at = COALESCE(
                expires_at,
                created_at + INTERVAL '24 hours',
                NOW() + INTERVAL '24 hours'
            )
            WHERE expires_at IS NULL
            """
        )
    )
    op.alter_column(
        "sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=True,
    )

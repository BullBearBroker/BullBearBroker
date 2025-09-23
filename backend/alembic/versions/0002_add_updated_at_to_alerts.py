"""add updated_at column to alerts"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_updated_at_to_alerts"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("alerts", "updated_at")

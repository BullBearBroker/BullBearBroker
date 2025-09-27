"""add title and active columns to alerts"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_title_active_to_alerts"
down_revision = "0006_add_risk_profile_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=False))  # [Codex] nuevo
        batch_op.add_column(  # [Codex] nuevo
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    # Ajustar server_default para futuros inserts
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.alter_column("active", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_column("active")
        batch_op.drop_column("title")

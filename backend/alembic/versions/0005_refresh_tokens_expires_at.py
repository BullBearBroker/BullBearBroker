"""add expires_at to refresh_tokens

# QA 2.7-H: restored operational migration after bridge
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_refresh_tokens_expires_at"
# QA: sincronizar con puente acortado para bases locales
down_revision = "0005_refresh_tokens_bridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # QA 2.7-H: agrega columna expires_at a refresh_tokens (solo si falta)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("refresh_tokens")}
    if "expires_at" not in columns:
        op.add_column(
            "refresh_tokens",
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # QA 2.7-H: revierte columna expires_at si existe
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("refresh_tokens")}
    if "expires_at" in columns:
        op.drop_column("refresh_tokens", "expires_at")

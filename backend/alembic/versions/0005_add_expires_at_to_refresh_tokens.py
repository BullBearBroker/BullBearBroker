"""add expires_at to refresh_tokens"""

from alembic import op
import sqlalchemy as sa


# ✅ Usa un string único para esta migración
revision = "0005_refresh_tokens_expires_at"
down_revision = "0004_create_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 🚀 Agregar columna expires_at a la tabla refresh_tokens
    op.add_column(
        "refresh_tokens",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # 🔄 Quitar la columna si se hace rollback
    op.drop_column("refresh_tokens", "expires_at")

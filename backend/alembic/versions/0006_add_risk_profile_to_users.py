"""add risk_profile to users"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_risk_profile_to_users"
down_revision = "0005_add_expires_at_to_refresh_tokens"
branch_labels = None
depends_on = None

risk_profile_enum = sa.Enum(  # [Codex] nuevo
    "conservador", "moderado", "agresivo", name="risk_profile_enum", native_enum=False
)


def upgrade() -> None:
    bind = op.get_bind()
    risk_profile_enum.create(bind, checkfirst=True)  # [Codex] nuevo
    op.add_column(
        "users",
        sa.Column("risk_profile", risk_profile_enum, nullable=True),  # [Codex] nuevo
    )


def downgrade() -> None:
    op.drop_column("users", "risk_profile")  # [Codex] nuevo
    bind = op.get_bind()
    risk_profile_enum.drop(bind, checkfirst=True)  # [Codex] nuevo

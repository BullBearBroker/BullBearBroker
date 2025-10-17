"""add risk_profile to users"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_user_risk_profile"
down_revision = "0005_refresh_tokens_expires_at"
branch_labels = None
depends_on = None

risk_profile_enum = sa.Enum(  # [Codex] nuevo
    "conservador", "moderado", "agresivo", name="risk_profile_enum", native_enum=False
)


def upgrade() -> None:
    bind = op.get_bind()
    risk_profile_enum.create(bind, checkfirst=True)  # [Codex] nuevo
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "risk_profile" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "risk_profile", risk_profile_enum, nullable=True
            ),  # [Codex] nuevo
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "risk_profile" in columns:
        op.drop_column("users", "risk_profile")  # [Codex] nuevo
    risk_profile_enum.drop(bind, checkfirst=True)  # [Codex] nuevo

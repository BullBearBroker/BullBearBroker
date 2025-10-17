"""Add MFA and push expiration columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# QA 2.4: Schema parity with Supabase (MFA + Push Expiration)

# revision identifiers, used by Alembic.
# QA: acortamos identificador para mantener compatibilidad con varchar(32)
revision = "0011_mfa_push_exp_columns"
down_revision = "0010_portfolios_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MFA columns
    with op.batch_alter_table("users", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "mfa_enabled" not in columns:
            batch_op.add_column(
                sa.Column(
                    "mfa_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default="false",
                )
            )
        if "mfa_secret" not in columns:
            batch_op.add_column(
                sa.Column("mfa_secret", sa.String(length=255), nullable=True)
            )

    # Push expiration column
    with op.batch_alter_table("push_subscriptions", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("push_subscriptions")}
        if "expiration_time" not in columns:
            batch_op.add_column(
                sa.Column(
                    "expiration_time",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("push_subscriptions", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("push_subscriptions")}
        if "expiration_time" in columns:
            batch_op.drop_column("expiration_time")

    with op.batch_alter_table("users", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "mfa_secret" in columns:
            batch_op.drop_column("mfa_secret")
        if "mfa_enabled" in columns:
            batch_op.drop_column("mfa_enabled")

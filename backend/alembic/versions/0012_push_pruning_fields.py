"""Add pruning metadata to push subscriptions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_push_pruning_fields"
down_revision = "0011_mfa_push_exp_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("push_subscriptions", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("push_subscriptions")}

        if "fail_count" not in columns:
            batch_op.add_column(
                sa.Column(
                    "fail_count", sa.Integer(), nullable=False, server_default="0"
                )
            )
        if "last_fail_at" not in columns:
            batch_op.add_column(
                sa.Column("last_fail_at", sa.DateTime(timezone=True), nullable=True)
            )
        if "pruning_marked" not in columns:
            batch_op.add_column(
                sa.Column(
                    "pruning_marked",
                    sa.Boolean(),
                    nullable=False,
                    server_default="false",
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("push_subscriptions", schema=None) as batch_op:
        bind = batch_op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns("push_subscriptions")}

        if "pruning_marked" in columns:
            batch_op.drop_column("pruning_marked")
        if "last_fail_at" in columns:
            batch_op.drop_column("last_fail_at")
        if "fail_count" in columns:
            batch_op.drop_column("fail_count")

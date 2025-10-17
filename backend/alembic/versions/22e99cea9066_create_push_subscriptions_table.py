import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

"""create push_subscriptions table"""

revision = "22e99cea9066"
down_revision = "0009_chat_push_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "push_subscriptions" not in existing_tables:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("endpoint", sa.String(), nullable=False),
            sa.Column("auth", sa.String(), nullable=False),
            sa.Column("p256dh", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "push_subscriptions" in inspector.get_table_names():
        op.drop_table("push_subscriptions")

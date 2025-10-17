"""Create portfolio_items table"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_create_portfolio_table"
down_revision = "0007_alerts_title_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "portfolio_items" not in inspector.get_table_names():
        op.create_table(
            "portfolio_items",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("symbol", sa.String(length=20), nullable=False),
            sa.Column("amount", sa.Numeric(20, 8), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            op.f("ix_portfolio_items_user_id"),
            "portfolio_items",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_portfolio_items_symbol"),
            "portfolio_items",
            ["symbol"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "portfolio_items" in inspector.get_table_names():
        op.drop_index(op.f("ix_portfolio_items_symbol"), table_name="portfolio_items")
        op.drop_index(op.f("ix_portfolio_items_user_id"), table_name="portfolio_items")
        op.drop_table("portfolio_items")

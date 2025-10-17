"""create portfolios and positions tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# QA: acortamos el identificador para respetar límite varchar(32)
revision = "0010_portfolios_positions"
down_revision = "create_advanced_alerts_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "portfolios" not in existing_tables:
        op.create_table(
            "portfolios",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column(
                "base_ccy", sa.String(length=10), nullable=False, server_default="USD"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
        )

    if "positions" not in existing_tables:
        op.create_table(
            "positions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
                primary_key=True,
            ),
            sa.Column(
                "portfolio_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("symbol", sa.String(length=40), nullable=False),
            sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
            sa.Column("avg_price", sa.Numeric(24, 8), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index(
            op.f("ix_positions_portfolio_id"),
            "positions",
            ["portfolio_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_positions_symbol"),
            "positions",
            ["symbol"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "positions" in tables:
        op.drop_index(op.f("ix_positions_symbol"), table_name="positions")
        op.drop_index(op.f("ix_positions_portfolio_id"), table_name="positions")
        op.drop_table("positions")
    if "portfolios" in tables:
        op.drop_table("portfolios")

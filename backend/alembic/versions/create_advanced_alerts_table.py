"""create advanced alerts table"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "create_advanced_alerts_table"
down_revision = "22e99cea9066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    delivery_enum = sa.Enum(
        "push",
        "email",
        "inapp",
        name="alert_delivery_method",
        native_enum=False,
    )
    bind = op.get_bind()
    delivery_enum.create(bind, checkfirst=True)

    with op.batch_alter_table("alerts", schema=None) as batch_op:
        # Renombrar la columna de condición previa a un campo legible legacy
        batch_op.alter_column(
            "condition",
            new_column_name="condition_expression",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "condition_expression",
            existing_type=sa.String(length=255),
            nullable=True,
        )

        batch_op.add_column(
            sa.Column(
                "name",
                sa.String(length=255),
                nullable=False,
                server_default="Nueva alerta",
            ),
        )
        batch_op.add_column(
            sa.Column(
                "condition",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "delivery_method",
                delivery_enum,
                nullable=False,
                server_default="push",
            )
        )
        batch_op.add_column(
            sa.Column(
                "pending_delivery",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.alter_column(
            "title", existing_type=sa.String(length=255), nullable=True
        )
        batch_op.alter_column(
            "asset", existing_type=sa.String(length=50), nullable=True
        )
        batch_op.alter_column("value", existing_type=sa.Float(), nullable=True)

        # Limpiar defaults temporales para nuevos registros
        batch_op.alter_column("name", server_default=None)
        batch_op.alter_column("condition", server_default=None)


def downgrade() -> None:
    delivery_enum = sa.Enum(
        "push",
        "email",
        "inapp",
        name="alert_delivery_method",
        native_enum=False,
    )

    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.alter_column("value", existing_type=sa.Float(), nullable=False)
        batch_op.alter_column(
            "asset", existing_type=sa.String(length=50), nullable=False
        )
        batch_op.alter_column(
            "title", existing_type=sa.String(length=255), nullable=False
        )
        batch_op.drop_column("pending_delivery")
        batch_op.drop_column("delivery_method")
        batch_op.drop_column("condition")
        batch_op.drop_column("name")
        batch_op.alter_column(
            "condition_expression",
            new_column_name="condition",
            existing_type=sa.String(length=255),
            nullable=False,
            server_default=">",
        )
        batch_op.alter_column(
            "condition",
            existing_type=sa.String(length=255),
            nullable=False,
        )

    bind = op.get_bind()
    delivery_enum.drop(bind, checkfirst=True)

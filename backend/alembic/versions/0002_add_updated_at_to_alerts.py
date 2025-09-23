"""no-op: updated_at ya está en 0001_initial_schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_updated_at_to_alerts"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Esta migración se marca como aplicada pero no hace nada,
    # porque la columna updated_at ya existe en 0001_initial_schema.
    pass


def downgrade() -> None:
    # No hay cambios que revertir.
    pass

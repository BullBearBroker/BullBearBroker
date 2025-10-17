"""# QA 2.7-H: bridge for remote 0005 (no-op)

Este puente alinea el historial remoto que referencia
'0005_add_expires_at_to_refresh_tokens'. No realiza cambios de esquema.
"""

# Alembic identifiers
# QA: acortamos el identificador para respetar límite varchar(32)
revision = "0005_refresh_tokens_bridge"
down_revision = "0004_create_refresh_tokens"  # QA 2.7-H: enlaza con la 0004 local
branch_labels = None
depends_on = None


def upgrade() -> None:
    # QA 2.7-H: no-op bridge migration
    pass


def downgrade() -> None:
    # QA 2.7-H: no-op
    pass

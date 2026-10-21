
"""Preserve document IDs in append-only audit logs."""

from alembic import op

revision = "d7a2c9e4b105"
down_revision = "c4e1a8b29f70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "audit_logs_document_id_fkey",
        "audit_logs",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "audit_logs_document_id_fkey",
        "audit_logs",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )

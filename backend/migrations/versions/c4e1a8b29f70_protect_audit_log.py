"""Protect audit logs from updates, deletes, and truncation."""

from alembic import op

revision = "c4e1a8b29f70"
down_revision = "96d86a251001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_audit_log_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs are append-only';
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_no_update_delete
        BEFORE UPDATE OR DELETE ON public.audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION public.prevent_audit_log_mutation();
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_no_truncate
        BEFORE TRUNCATE ON public.audit_logs
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.prevent_audit_log_mutation();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS audit_logs_no_truncate
        ON public.audit_logs;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS audit_logs_no_update_delete
        ON public.audit_logs;
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS public.prevent_audit_log_mutation();
    """)
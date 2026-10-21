
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import engine


def test_audit_log_rejects_update():
    with engine.begin() as connection:
        audit_id = connection.execute(
            text("""
                INSERT INTO audit_logs
                    (action, outcome, details)
                VALUES
                    ('integrity_test_update', 'success',
                     'temporary test record')
                RETURNING id
            """)
        ).scalar_one()

    try:
        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(
                    text("""
                        UPDATE audit_logs
                        SET details = 'modified'
                        WHERE id = :audit_id
                    """),
                    {"audit_id": audit_id},
                )

        with engine.connect() as connection:
            details = connection.execute(
                text("""
                    SELECT details FROM audit_logs WHERE id = :audit_id
                """),
                {"audit_id": audit_id},
            ).scalar_one()

        assert details == "temporary test record"
    finally:
        pass


def test_audit_log_rejects_delete():
    with engine.begin() as connection:
        audit_id = connection.execute(
            text("""
                INSERT INTO audit_logs
                    (action, outcome, details)
                VALUES
                    ('integrity_test_delete', 'success',
                     'temporary test record')
                RETURNING id
            """)
        ).scalar_one()

    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM audit_logs WHERE id = :audit_id"),
                {"audit_id": audit_id},
            )

    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM audit_logs WHERE id = :audit_id)"),
            {"audit_id": audit_id},
        ).scalar_one()

    assert exists is True


def test_audit_log_rejects_truncate():
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE audit_logs"))

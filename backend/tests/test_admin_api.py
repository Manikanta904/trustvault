
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, User
from app.security import create_access_token, hash_password
from sqlalchemy import select

client = TestClient(app)


@pytest.fixture
def admin_test_accounts():
    suffix = uuid4().hex

    with SessionLocal() as db:
        users = [
            User(
                name="Test Admin",
                email=f"admin-{suffix}@example.com",
                password_hash=hash_password("TestOnly!Password123"),
                role="admin",
                is_active=True,
            ),
            User(
                name="Test Owner",
                email=f"owner-{suffix}@example.com",
                password_hash=hash_password("TestOnly!Password123"),
                role="owner",
                is_active=True,
            ),
            User(
                name="Test Viewer",
                email=f"viewer-{suffix}@example.com",
                password_hash=hash_password("TestOnly!Password123"),
                role="viewer",
                is_active=True,
            ),
        ]

        db.add_all(users)
        db.commit()

        for user in users:
            db.refresh(user)

        result = {
            "admin": {
                "id": users[0].id,
                "token": create_access_token(users[0]),
            },
            "owner": {
                "id": users[1].id,
                "token": create_access_token(users[1]),
            },
            "viewer": {
                "id": users[2].id,
                "token": create_access_token(users[2]),
            },
        }

    yield result


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_audit_logs_require_authentication():
    response = client.get("/admin/audit-logs")
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["owner", "viewer"])
def test_non_admin_cannot_read_audit_logs(admin_test_accounts, role):
    token = admin_test_accounts[role]["token"]

    response = client.get(
        "/admin/audit-logs",
        headers=auth(token),
    )

    assert response.status_code == 403


def test_admin_can_read_audit_logs(admin_test_accounts):
    response = client.get(
        "/admin/audit-logs",
        headers=auth(admin_test_accounts["admin"]["token"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_admin_can_filter_audit_logs_by_action(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]

    with SessionLocal() as db:
        db.add_all([
            AuditLog(
                actor_id=admin_id,
                action="test_action_alpha",
                outcome="success",
                details="Test event alpha",
            ),
            AuditLog(
                actor_id=admin_id,
                action="test_action_beta",
                outcome="denied",
                details="Test event beta",
            ),
        ])
        db.commit()

    response = client.get(
        "/admin/audit-logs",
        params={"action": "test_action_alpha"},
        headers=auth(token),
    )

    assert response.status_code == 200
    items = response.json()["items"]

    assert any(
        item["action"] == "test_action_alpha"
        and item["details"] == "Test event alpha"
        for item in items
    )
    assert all(
        item["action"] == "test_action_alpha"
        for item in items
    )


def test_admin_can_filter_audit_logs_by_outcome(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]

    with SessionLocal() as db:
        db.add(
            AuditLog(
                actor_id=admin_id,
                action="test_denied_event",
                outcome="denied",
                details="Test denied event",
            )
        )
        db.commit()

    response = client.get(
        "/admin/audit-logs",
        params={"outcome": "denied"},
        headers=auth(token),
    )

    assert response.status_code == 200
    items = response.json()["items"]

    assert any(
        item["action"] == "test_denied_event"
        and item["outcome"] == "denied"
        for item in items
    )
    assert all(item["outcome"] == "denied" for item in items)


def test_admin_audit_log_pagination(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]
    action = f"pagination_{uuid4().hex}"

    with SessionLocal() as db:
        db.add_all(
            [
                AuditLog(
                    actor_id=admin_id,
                    action=action,
                    outcome="success",
                    details=f"Pagination test record {index}",
                )
                for index in range(3)
            ]
        )
        db.commit()

    first_response = client.get(
        "/admin/audit-logs",
        params={"action": action, "limit": 2, "offset": 0},
        headers=auth(token),
    )
    second_response = client.get(
        "/admin/audit-logs",
        params={"action": action, "limit": 2, "offset": 2},
        headers=auth(token),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_body = first_response.json()
    second_body = second_response.json()

    first_ids = {item["id"] for item in first_body["items"]}
    second_ids = {item["id"] for item in second_body["items"]}

    assert len(first_ids) == 2
    assert len(second_ids) == 1
    assert first_ids.isdisjoint(second_ids)
    assert first_body["limit"] == 2
    assert second_body["offset"] == 2


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"outcome": "unknown"}, 422),
        ({"limit": 0}, 422),
        ({"limit": 101}, 422),
        ({"offset": -1}, 422),
        (
            {
                "start_date": "2026-10-20T00:00:00",
                "end_date": "2026-10-19T00:00:00",
            },
            422,
        ),
    ],
)
def test_admin_audit_log_rejects_invalid_filters(
    admin_test_accounts, params, expected_status
):
    response = client.get(
        "/admin/audit-logs",
        params=params,
        headers=auth(admin_test_accounts["admin"]["token"]),
    )

    assert response.status_code == expected_status


def test_admin_can_filter_audit_logs_by_actor(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]
    action = f"actor_filter_{uuid4().hex}"

    with SessionLocal() as db:
        db.add(
            AuditLog(
                actor_id=admin_id,
                action=action,
                outcome="success",
                details="Actor filter test",
            )
        )
        db.commit()

    response = client.get(
        "/admin/audit-logs",
        params={"actor_id": admin_id, "action": action},
        headers=auth(token),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["actor_id"] == admin_id for item in items)
    assert all(item["action"] == action for item in items)


def test_admin_can_filter_audit_logs_by_date_range(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]
    action = f"date_filter_{uuid4().hex}"

    with SessionLocal() as db:
        db.add(
            AuditLog(
                actor_id=admin_id,
                action=action,
                outcome="success",
                details="Date filter test",
            )
        )
        db.commit()

    response = client.get(
        "/admin/audit-logs",
        params={
            "action": action,
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2027-01-01T00:00:00",
        },
        headers=auth(token),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["action"] == action for item in items)


def test_admin_can_filter_audit_logs_by_document_id(admin_test_accounts):
    admin_id = admin_test_accounts["admin"]["id"]
    token = admin_test_accounts["admin"]["token"]
    action = f"doc_filter_{uuid4().hex}"
    target_doc_id = 88888

    with SessionLocal() as db:
        db.add_all([
            AuditLog(
                actor_id=admin_id,
                action=action,
                outcome="success",
                document_id=target_doc_id,
                details="Document filter target",
            ),
            AuditLog(
                actor_id=admin_id,
                action=action,
                outcome="success",
                document_id=99999,
                details="Other document",
            ),
        ])
        db.commit()

    response = client.get(
        "/admin/audit-logs",
        params={"action": action, "document_id": target_doc_id},
        headers=auth(token),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["document_id"] == target_doc_id
    assert items[0]["details"] == "Document filter target"


def test_admin_audit_log_rejects_invalid_document_id(admin_test_accounts):
    token = admin_test_accounts["admin"]["token"]

    response = client.get(
        "/admin/audit-logs",
        params={"document_id": 0},
        headers=auth(token),
    )
    assert response.status_code == 422


def test_non_admin_audit_log_denial_is_audited(admin_test_accounts):
    viewer_id = admin_test_accounts["viewer"]["id"]
    viewer_token = admin_test_accounts["viewer"]["token"]

    response = client.get(
        "/admin/audit-logs",
        headers=auth(viewer_token),
    )
    assert response.status_code == 403

    with SessionLocal() as db:
        denied_entry = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == viewer_id,
                AuditLog.action == "admin_audit_logs_read",
                AuditLog.outcome == "denied",
            )
            .order_by(AuditLog.id.desc())
        )

    assert denied_entry is not None
    assert "Non-admin attempted to access audit logs" in denied_entry.details

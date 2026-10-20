
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, User
from app.security import create_access_token, hash_password

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

    # Remove only audit records and users created for this fixture.
    user_ids = [
        result["admin"]["id"],
        result["owner"]["id"],
        result["viewer"]["id"],
    ]

    with SessionLocal() as db:
        db.execute(
            delete(AuditLog).where(AuditLog.actor_id.in_(user_ids))
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


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
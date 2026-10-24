from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentPermission, User
from app.security import create_access_token, hash_password
import app.file_storage as file_storage

client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sharing_test_env(tmp_path, monkeypatch):
    """Set up isolated storage and test accounts for Phase 2 user search & sharing tests."""
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    suffix = uuid4().hex
    with SessionLocal() as db:
        owner_alice = User(
            name=f"Alice Smith {suffix}",
            email=f"alice-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        owner_bob = User(
            name=f"Bob Jones {suffix}",
            email=f"bob-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        viewer_carol = User(
            name=f"Carol Viewer {suffix}",
            email=f"carol-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="viewer",
            is_active=True,
        )
        inactive_dan = User(
            name=f"Dan Inactive {suffix}",
            email=f"dan-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=False,
        )
        db.add_all([owner_alice, owner_bob, viewer_carol, inactive_dan])
        db.commit()

        for u in [owner_alice, owner_bob, viewer_carol, inactive_dan]:
            db.refresh(u)

        env = {
            "alice": {"id": owner_alice.id, "name": owner_alice.name, "email": owner_alice.email, "token": create_access_token(owner_alice)},
            "bob": {"id": owner_bob.id, "name": owner_bob.name, "email": owner_bob.email, "token": create_access_token(owner_bob)},
            "carol": {"id": viewer_carol.id, "name": viewer_carol.name, "email": viewer_carol.email, "token": create_access_token(viewer_carol)},
            "dan": {"id": inactive_dan.id, "name": inactive_dan.name, "email": inactive_dan.email, "token": create_access_token(inactive_dan)},
            "suffix": suffix,
            "tmp_path": tmp_path,
        }

    yield env


def test_authenticated_employee_search_by_name_and_email(sharing_test_env):
    """Verify authenticated document owners can search employees by partial name or email."""
    alice_token = sharing_test_env["alice"]["token"]
    bob_email = sharing_test_env["bob"]["email"]
    suffix = sharing_test_env["suffix"]

    # Search by name fragment with test suffix
    res_name = client.get(
        "/users/search",
        params={"q": f"Bob Jones {suffix}"},
        headers=auth_header(alice_token),
    )
    assert res_name.status_code == 200
    items = res_name.json()
    assert len(items) >= 1
    assert any(u["id"] == sharing_test_env["bob"]["id"] for u in items)

    # Search by exact/partial email
    res_email = client.get(
        "/users/search",
        params={"q": f"bob-{suffix}"},
        headers=auth_header(alice_token),
    )
    assert res_email.status_code == 200
    items_email = res_email.json()
    assert len(items_email) == 1
    assert items_email[0]["email"] == bob_email
    assert items_email[0]["name"] == sharing_test_env["bob"]["name"]
    assert items_email[0]["role"] == "owner"


def test_unauthorized_user_search_requests(sharing_test_env):
    """Verify unauthenticated callers (401) and viewer role (403) are denied employee search."""
    # 1. Anonymous request
    anon_res = client.get("/users/search", params={"q": "Bob"})
    assert anon_res.status_code == 401

    # 2. Viewer role request
    viewer_token = sharing_test_env["carol"]["token"]
    viewer_id = sharing_test_env["carol"]["id"]
    viewer_res = client.get(
        "/users/search",
        params={"q": "Bob"},
        headers=auth_header(viewer_token),
    )
    assert viewer_res.status_code == 403

    # Verify denial audit log was persisted
    with SessionLocal() as db:
        denial = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == viewer_id,
                AuditLog.action == "user_search",
                AuditLog.outcome == "denied",
            )
        )
        assert denial is not None
        assert "viewer" in denial.details


def test_minimal_response_fields(sharing_test_env):
    """Verify user search response returns ONLY minimal non-sensitive fields."""
    alice_token = sharing_test_env["alice"]["token"]
    suffix = sharing_test_env["suffix"]

    res = client.get(
        "/users/search",
        params={"q": suffix},
        headers=auth_header(alice_token),
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0

    allowed_keys = {"id", "name", "email", "role"}
    for item in data:
        assert set(item.keys()) == allowed_keys
        assert "password" not in item
        assert "password_hash" not in item
        assert "is_active" not in item


def test_inactive_users_are_excluded_from_search(sharing_test_env):
    """Verify inactive employee accounts are never returned in search results."""
    alice_token = sharing_test_env["alice"]["token"]
    suffix = sharing_test_env["suffix"]

    # Search specifically for Dan Inactive
    res = client.get(
        "/users/search",
        params={"q": f"Dan Inactive {suffix}"},
        headers=auth_header(alice_token),
    )
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_query_and_result_limit_validation(sharing_test_env):
    """Verify query bounds, limit constraints, and enumeration defenses."""
    alice_token = sharing_test_env["alice"]["token"]

    # Limit bounds: 0 rejected (422), 51 rejected (422)
    assert client.get("/users/search", params={"q": "a", "limit": 0}, headers=auth_header(alice_token)).status_code == 422
    assert client.get("/users/search", params={"q": "a", "limit": 51}, headers=auth_header(alice_token)).status_code == 422

    # Query length > 100 rejected (422)
    long_q = "x" * 101
    assert client.get("/users/search", params={"q": long_q}, headers=auth_header(alice_token)).status_code == 422

    # Whitespace-only query returns empty list safely
    ws_res = client.get("/users/search", params={"q": "   "}, headers=auth_header(alice_token))
    assert ws_res.status_code == 200
    assert ws_res.json() == []


def test_caller_cannot_search_themselves(sharing_test_env):
    """Verify caller is excluded from their own search results to prevent self-grants."""
    alice_token = sharing_test_env["alice"]["token"]
    alice_email = sharing_test_env["alice"]["email"]

    res = client.get(
        "/users/search",
        params={"q": alice_email},
        headers=auth_header(alice_token),
    )
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_document_permissions_listing_and_grant_workflow(sharing_test_env):
    """
    Test complete sharing lifecycle:
    1. Owner Alice uploads a document.
    2. Lists permissions -> empty.
    3. Searches for Bob (who has global role 'owner').
    4. Grants Bob 'read' access.
    5. Verifies Bob's global role in database remains 'owner' (NO role degradation!).
    6. Lists permissions -> shows Bob with permission_type='read' and user details.
    7. Upgrades Bob to 'edit'.
    8. Lists permissions -> shows Bob with permission_type='edit'.
    """
    alice_token = sharing_test_env["alice"]["token"]
    bob_id = sharing_test_env["bob"]["id"]
    bob_token = sharing_test_env["bob"]["token"]

    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "Project Alpha Plan")
    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()

    # 1. Alice uploads document
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(alice_token),
        files={"file": ("project_plan.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Project Alpha Plan"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Permissions list is initially empty
    perms_initial = client.get(
        f"/documents/{doc_id}/permissions",
        headers=auth_header(alice_token),
    )
    assert perms_initial.status_code == 200
    assert perms_initial.json() == []

    # 3. Grant 'read' permission to Bob
    grant_res = client.put(
        f"/documents/{doc_id}/permissions/{bob_id}",
        headers=auth_header(alice_token),
        json={"permission_type": "read"},
    )
    assert grant_res.status_code == 200

    # 4. Critical requirement check: Bob's global role remains 'owner' in the database!
    with SessionLocal() as db:
        bob_db = db.get(User, bob_id)
        assert bob_db is not None
        assert bob_db.role == "owner"

    # 5. Verify Bob can read metadata and view in-browser, and download watermarked copy
    assert client.get(f"/documents/{doc_id}", headers=auth_header(bob_token)).status_code == 200
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(bob_token)).status_code == 200
    bob_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(bob_token))
    assert bob_dl.status_code == 200
    assert bob_dl.content != pdf_bytes
    assert "attachment" in bob_dl.headers.get("content-disposition", "")
    alice_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(alice_token))
    assert alice_dl.status_code == 200
    assert alice_dl.content == pdf_bytes

    # 6. Bob cannot edit with read-only grant
    assert client.patch(f"/documents/{doc_id}", headers=auth_header(bob_token), json={"title": "Hacked"}).status_code == 404

    # 7. List permissions shows Bob's details
    perms_res = client.get(
        f"/documents/{doc_id}/permissions",
        headers=auth_header(alice_token),
    )
    assert perms_res.status_code == 200
    p_list = perms_res.json()
    assert len(p_list) == 1
    assert p_list[0]["user_id"] == bob_id
    assert p_list[0]["user_name"] == sharing_test_env["bob"]["name"]
    assert p_list[0]["user_email"] == sharing_test_env["bob"]["email"]
    assert p_list[0]["permission_type"] == "read"

    # 8. Upgrade Bob to 'edit'
    upgrade_res = client.put(
        f"/documents/{doc_id}/permissions/{bob_id}",
        headers=auth_header(alice_token),
        json={"permission_type": "edit"},
    )
    assert upgrade_res.status_code == 200

    # 9. Verify Bob can now update metadata
    patch_res = client.patch(
        f"/documents/{doc_id}",
        headers=auth_header(bob_token),
        json={"title": "Project Alpha Plan - Revised by Bob"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Project Alpha Plan - Revised by Bob"

    # 10. List permissions shows updated 'edit' permission
    perms_updated = client.get(
        f"/documents/{doc_id}/permissions",
        headers=auth_header(alice_token),
    )
    assert perms_updated.status_code == 200
    assert perms_updated.json()[0]["permission_type"] == "edit"


def test_revoking_access_removes_from_permissions_list(sharing_test_env):
    """Verify revoking permission removes it from the permissions list and terminates access."""
    alice_token = sharing_test_env["alice"]["token"]
    bob_id = sharing_test_env["bob"]["id"]
    bob_token = sharing_test_env["bob"]["token"]

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(alice_token),
        files={"file": ("revocable.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Grant read
    client.put(f"/documents/{doc_id}/permissions/{bob_id}", headers=auth_header(alice_token), json={"permission_type": "read"})

    # Verify present in permissions list
    assert len(client.get(f"/documents/{doc_id}/permissions", headers=auth_header(alice_token)).json()) == 1

    # Revoke
    del_res = client.delete(f"/documents/{doc_id}/permissions/{bob_id}", headers=auth_header(alice_token))
    assert del_res.status_code == 204

    # Verify permissions list is now empty
    perms_after = client.get(f"/documents/{doc_id}/permissions", headers=auth_header(alice_token))
    assert perms_after.status_code == 200
    assert perms_after.json() == []

    # Verify Bob cannot access the document
    assert client.get(f"/documents/{doc_id}", headers=auth_header(bob_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(bob_token)).status_code == 404


def test_no_privilege_escalation_or_cross_document_leakage(sharing_test_env):
    """
    Verify:
    1. Bob (editor on doc 1) cannot list permissions of doc 1 (owner only).
    2. Bob cannot grant permissions on doc 1 to Carol.
    3. Bob cannot delete doc 1.
    4. Bob cannot access Alice's unshared doc 2.
    """
    alice_token = sharing_test_env["alice"]["token"]
    bob_id = sharing_test_env["bob"]["id"]
    bob_token = sharing_test_env["bob"]["token"]
    carol_id = sharing_test_env["carol"]["id"]

    doc1_res = client.post("/documents/upload", headers=auth_header(alice_token), files={"file": ("doc1.pdf", b"%PDF-1.4", "application/pdf")})
    doc2_res = client.post("/documents/upload", headers=auth_header(alice_token), files={"file": ("doc2.pdf", b"%PDF-1.4", "application/pdf")})
    doc1_id = doc1_res.json()["id"]
    doc2_id = doc2_res.json()["id"]

    # Grant edit to Bob on doc 1 only
    client.put(f"/documents/{doc1_id}/permissions/{bob_id}", headers=auth_header(alice_token), json={"permission_type": "edit"})

    # 1. Bob cannot inspect permissions list (owner only)
    assert client.get(f"/documents/{doc1_id}/permissions", headers=auth_header(bob_token)).status_code == 404

    # 2. Bob cannot grant permissions to Carol on doc 1
    assert client.put(f"/documents/{doc1_id}/permissions/{carol_id}", headers=auth_header(bob_token), json={"permission_type": "read"}).status_code == 404

    # 3. Bob cannot delete doc 1
    assert client.delete(f"/documents/{doc1_id}", headers=auth_header(bob_token)).status_code == 404

    # 4. Bob cannot access doc 2
    assert client.get(f"/documents/{doc2_id}", headers=auth_header(bob_token)).status_code == 404
    assert client.get(f"/documents/{doc2_id}/download", headers=auth_header(bob_token)).status_code == 404

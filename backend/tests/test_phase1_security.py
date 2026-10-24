from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentPermission, User
from app.security import JWT_SECRET, create_access_token, hash_password
import app.file_storage as file_storage

client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase1_test_env(tmp_path, monkeypatch):
    """Set up isolated storage directory and test accounts for Phase 1 tests."""
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    suffix = uuid4().hex
    with SessionLocal() as db:
        owner_a = User(
            name="Phase1 Owner A",
            email=f"owner-a-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        owner_b = User(
            name="Phase1 Owner B",
            email=f"owner-b-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        viewer = User(
            name="Phase1 Viewer",
            email=f"viewer-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="viewer",
            is_active=True,
        )
        admin = User(
            name="Phase1 Admin",
            email=f"admin-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="admin",
            is_active=True,
        )
        inactive_user = User(
            name="Phase1 Inactive",
            email=f"inactive-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="viewer",
            is_active=False,
        )
        db.add_all([owner_a, owner_b, viewer, admin, inactive_user])
        db.commit()

        for u in [owner_a, owner_b, viewer, admin, inactive_user]:
            db.refresh(u)

        env_data = {
            "owner_a": {"id": owner_a.id, "token": create_access_token(owner_a)},
            "owner_b": {"id": owner_b.id, "token": create_access_token(owner_b)},
            "viewer": {"id": viewer.id, "token": create_access_token(viewer)},
            "admin": {"id": admin.id, "token": create_access_token(admin)},
            "inactive_user": {"id": inactive_user.id, "token": create_access_token(inactive_user)},
            "storage_dir": tmp_path,
            "suffix": suffix,
        }

    yield env_data


def test_owner_a_cannot_read_or_download_owner_b_private_document(phase1_test_env):
    """Verify complete cross-user isolation: Owner A cannot read metadata or download Owner B's document."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    owner_a_token = phase1_test_env["owner_a"]["token"]
    owner_a_id = phase1_test_env["owner_a"]["id"]

    pdf_bytes = b"%PDF-1.4\nOwner B Confidential Document Content\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("b_private.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Owner B Classified PDF", "category": "Legal"},
    )
    assert upload_res.status_code == 201
    doc_b_id = upload_res.json()["id"]

    # Owner A attempts metadata read
    read_res = client.get(
        f"/documents/{doc_b_id}",
        headers=auth_header(owner_a_token),
    )
    assert read_res.status_code == 404

    # Owner A attempts download
    dl_res = client.get(
        f"/documents/{doc_b_id}/download",
        headers=auth_header(owner_a_token),
    )
    assert dl_res.status_code == 404

    # Verify both refused attempts are audited in the database
    with SessionLocal() as db:
        read_denial = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == owner_a_id,
                AuditLog.document_id == doc_b_id,
                AuditLog.action == "document_read",
                AuditLog.outcome == "denied",
            )
        )
        assert read_denial is not None

        dl_denial = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == owner_a_id,
                AuditLog.document_id == doc_b_id,
                AuditLog.action == "document_download",
                AuditLog.outcome == "denied",
            )
        )
        assert dl_denial is not None


def test_owner_a_cannot_edit_or_delete_owner_b_document(phase1_test_env):
    """Verify Owner A cannot modify metadata or delete Owner B's document."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    owner_a_token = phase1_test_env["owner_a"]["token"]
    owner_a_id = phase1_test_env["owner_a"]["id"]

    pdf_bytes = b"%PDF-1.4\nOwner B Financial Records\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("financial.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Q3 Financials", "category": "Finance"},
    )
    assert upload_res.status_code == 201
    doc_b_id = upload_res.json()["id"]

    # Owner A attempts edit
    edit_res = client.patch(
        f"/documents/{doc_b_id}",
        headers=auth_header(owner_a_token),
        json={"title": "Tampered Title by Owner A"},
    )
    assert edit_res.status_code == 404

    # Owner A attempts delete
    del_res = client.delete(
        f"/documents/{doc_b_id}",
        headers=auth_header(owner_a_token),
    )
    assert del_res.status_code == 404

    # Verify Owner B's document in the DB was unmodified
    with SessionLocal() as db:
        doc = db.get(Document, doc_b_id)
        assert doc is not None
        assert doc.title == "Q3 Financials"

        edit_denial = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == owner_a_id,
                AuditLog.document_id == doc_b_id,
                AuditLog.action == "document_edit",
                AuditLog.outcome == "denied",
            )
        )
        assert edit_denial is not None

        delete_denial = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == owner_a_id,
                AuditLog.document_id == doc_b_id,
                AuditLog.action == "document_delete",
                AuditLog.outcome == "denied",
            )
        )
        assert delete_denial is not None


def test_viewer_cannot_access_unshared_documents(phase1_test_env):
    """Verify an ungranted viewer cannot read, download, edit, delete, or manage permissions."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    viewer_token = phase1_test_env["viewer"]["token"]
    viewer_id = phase1_test_env["viewer"]["id"]

    pdf_bytes = b"%PDF-1.4\nViewer Restricted Document\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("restricted.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Restricted Document", "category": "Internal"},
    )
    doc_id = upload_res.json()["id"]

    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token)).status_code == 404
    assert client.patch(f"/documents/{doc_id}", headers=auth_header(viewer_token), json={"title": "Change"}).status_code == 404
    assert client.delete(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 404
    assert client.put(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(viewer_token), json={"permission_type": "read"}).status_code == 404
    assert client.delete(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(viewer_token)).status_code == 404


def test_url_tampering_document_ids_does_not_bypass_authorization(phase1_test_env):
    """Verify changing IDs in URLs returns 404 and does not reveal document existence or data."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    viewer_token = phase1_test_env["viewer"]["token"]
    viewer_id = phase1_test_env["viewer"]["id"]

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("tamper_test.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"title": "Tamper Test"},
    )
    real_id = upload_res.json()["id"]

    tampered_ids = [real_id + 1, real_id + 99999, 987654, -1]

    for tid in tampered_ids:
        assert client.get(f"/documents/{tid}", headers=auth_header(viewer_token)).status_code in (404, 422)
        assert client.get(f"/documents/{tid}/download", headers=auth_header(viewer_token)).status_code in (404, 422)
        assert client.patch(f"/documents/{tid}", headers=auth_header(viewer_token), json={"title": "X"}).status_code in (404, 422)
        assert client.delete(f"/documents/{tid}", headers=auth_header(viewer_token)).status_code in (404, 422)
        assert client.put(f"/documents/{tid}/permissions/{viewer_id}", headers=auth_header(viewer_token), json={"permission_type": "read"}).status_code in (404, 422)


def test_forged_or_unauthorized_grants_are_rejected(phase1_test_env):
    """Verify unauthorized or forged permission grants cannot be created."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    owner_b_id = phase1_test_env["owner_b"]["id"]
    owner_a_token = phase1_test_env["owner_a"]["token"]
    viewer_token = phase1_test_env["viewer"]["token"]
    viewer_id = phase1_test_env["viewer"]["id"]
    inactive_id = phase1_test_env["inactive_user"]["id"]

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("grant_target.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # 1. Non-owner (Owner A) attempts to grant access to Owner B's document
    res1 = client.put(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(owner_a_token),
        json={"permission_type": "read"},
    )
    assert res1.status_code == 404

    # 2. Viewer attempts to grant access
    res2 = client.put(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(viewer_token),
        json={"permission_type": "read"},
    )
    assert res2.status_code == 404

    # 3. Forged non-existent target user ID
    res3 = client.put(
        f"/documents/{doc_id}/permissions/9999999",
        headers=auth_header(owner_b_token),
        json={"permission_type": "read"},
    )
    assert res3.status_code == 404

    # 4. Inactive target user
    res4 = client.put(
        f"/documents/{doc_id}/permissions/{inactive_id}",
        headers=auth_header(owner_b_token),
        json={"permission_type": "read"},
    )
    assert res4.status_code == 404

    # 5. Owner granting to themselves
    res5 = client.put(
        f"/documents/{doc_id}/permissions/{owner_b_id}",
        headers=auth_header(owner_b_token),
        json={"permission_type": "read"},
    )
    assert res5.status_code == 400


def test_invalid_expired_missing_tokens_rejected(phase1_test_env):
    """Verify that protected endpoints reject missing, malformed, forged, or expired tokens."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("token_test.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    endpoints = [
        ("GET", "/documents"),
        ("GET", f"/documents/{doc_id}"),
        ("GET", f"/documents/{doc_id}/download"),
        ("GET", "/admin/audit-logs"),
        ("GET", "/auth/me"),
    ]

    # 1. Missing Authorization header
    for method, path in endpoints:
        res = client.request(method, path)
        assert res.status_code == 401

    # 2. Malformed token
    for method, path in endpoints:
        res = client.request(method, path, headers={"Authorization": "Bearer not-a-valid-jwt"})
        assert res.status_code == 401

    # 3. Forged signature (signed with an untrusted secret)
    forged_token = jwt.encode(
        {"sub": str(phase1_test_env["owner_b"]["id"]), "role": "owner", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "completely-wrong-untrusted-secret-key-12345",
        algorithm="HS256",
    )
    for method, path in endpoints:
        res = client.request(method, path, headers=auth_header(forged_token))
        assert res.status_code == 401

    # 4. Expired token
    expired_token = jwt.encode(
        {"sub": str(phase1_test_env["owner_b"]["id"]), "role": "owner", "exp": datetime.now(timezone.utc) - timedelta(minutes=10)},
        JWT_SECRET,
        algorithm="HS256",
    )
    for method, path in endpoints:
        res = client.request(method, path, headers=auth_header(expired_token))
        assert res.status_code == 401


def test_listing_and_search_do_not_leak_unauthorized_documents(phase1_test_env):
    """Verify document listing and search never expose unshared documents or their metadata."""
    owner_b_token = phase1_test_env["owner_b"]["token"]
    owner_b_id = phase1_test_env["owner_b"]["id"]
    owner_a_token = phase1_test_env["owner_a"]["token"]
    viewer_token = phase1_test_env["viewer"]["token"]
    unique_keyword = f"TopSecretProject-{phase1_test_env['suffix']}"

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("confidential.pdf", b"%PDF-1.4 classified", "application/pdf")},
        data={"title": f"Document {unique_keyword}", "category": "M&A"},
    )
    doc_b_id = upload_res.json()["id"]

    for token in [owner_a_token, viewer_token]:
        # General listing
        list_res = client.get("/documents", headers=auth_header(token))
        assert list_res.status_code == 200
        assert doc_b_id not in {item["id"] for item in list_res.json()}

        # Keyword search
        search_res = client.get("/documents", params={"search": unique_keyword}, headers=auth_header(token))
        assert search_res.status_code == 200
        assert len(search_res.json()) == 0

        # Owner filter targeting Owner B
        owner_filter_res = client.get("/documents", params={"owner_id": owner_b_id}, headers=auth_header(token))
        assert owner_filter_res.status_code == 200
        assert len(owner_filter_res.json()) == 0

        # Category filter targeting Owner B's category
        cat_filter_res = client.get("/documents", params={"category": "M&A"}, headers=auth_header(token))
        assert cat_filter_res.status_code == 200
        assert doc_b_id not in {item["id"] for item in cat_filter_res.json()}


def test_immediate_revocation_lifecycle(phase1_test_env):
    """
    Standard 3 Verification:
    Grant a user read access, verify access works, revoke the grant,
    then use the SAME still-valid login token to make fresh requests.
    Every subsequent request must re-evaluate live database permissions and immediately block access.
    """
    owner_b_token = phase1_test_env["owner_b"]["token"]
    viewer_token = phase1_test_env["viewer"]["token"]
    viewer_id = phase1_test_env["viewer"]["id"]

    raw_file_bytes = b"%PDF-1.4\nImmediate Revocation Contract Text\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("contract.pdf", raw_file_bytes, "application/pdf")},
        data={"title": "Customer Service Agreement", "category": "Contracts"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 1. Before grant: Viewer is blocked with HTTP 404
    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token)).status_code == 404

    # 2. Owner grants read permission
    grant_res = client.put(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(owner_b_token),
        json={"permission_type": "read"},
    )
    assert grant_res.status_code == 200

    # 3. Viewer immediately has read and download access
    read_res = client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert read_res.status_code == 200
    assert read_res.json()["title"] == "Customer Service Agreement"

    download_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token))
    assert download_res.status_code == 200
    assert download_res.content == raw_file_bytes

    list_res = client.get("/documents", headers=auth_header(viewer_token))
    assert doc_id in {item["id"] for item in list_res.json()}

    # 4. Owner revokes permission
    revoke_res = client.delete(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(owner_b_token),
    )
    assert revoke_res.status_code == 204

    # 5. Using the EXACT SAME still-valid login token (no new login, token remains valid):
    # Every subsequent request must re-evaluate current database permissions and return 404.
    post_revoke_read = client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert post_revoke_read.status_code == 404

    post_revoke_download = client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token))
    assert post_revoke_download.status_code == 404

    post_revoke_patch = client.patch(
        f"/documents/{doc_id}",
        headers=auth_header(viewer_token),
        json={"title": "Hacked after revoke"},
    )
    assert post_revoke_patch.status_code == 404

    post_revoke_delete = client.delete(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert post_revoke_delete.status_code == 404

    post_revoke_list = client.get("/documents", headers=auth_header(viewer_token))
    assert doc_id not in {item["id"] for item in post_revoke_list.json()}

    post_revoke_search = client.get("/documents", params={"search": "Customer Service Agreement"}, headers=auth_header(viewer_token))
    assert doc_id not in {item["id"] for item in post_revoke_search.json()}

    # 6. Verify audit logs record the revocation and the post-revocation denied attempts
    with SessionLocal() as db:
        revoke_log = db.scalar(
            select(AuditLog).where(
                AuditLog.document_id == doc_id,
                AuditLog.action == "permission_revoke",
                AuditLog.outcome == "success",
            )
        )
        assert revoke_log is not None

        denied_read_log = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == viewer_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "document_read",
                AuditLog.outcome == "denied",
            )
        )
        assert denied_read_log is not None

        denied_download_log = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == viewer_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "document_download",
                AuditLog.outcome == "denied",
            )
        )
        assert denied_download_log is not None


def test_audit_trail_completeness_and_denial_recording(phase1_test_env):
    """
    Standard 2 Verification:
    Verify the application logs successful and refused attempts for:
    - Uploads (success, non-owner denied, invalid content failure)
    - Downloads (success, ungranted user denied)
    - Document changes (success, viewer edit denied, empty update failure)
    - Deletions (success, non-owner denied)
    - Permission grants and revocations (success, unauthorized denied, invalid user failure)
    """
    owner_b_token = phase1_test_env["owner_b"]["token"]
    owner_b_id = phase1_test_env["owner_b"]["id"]
    viewer_token = phase1_test_env["viewer"]["token"]
    viewer_id = phase1_test_env["viewer"]["id"]

    # 1. Uploads
    # Non-owner denied
    up_denied = client.post(
        "/documents/upload",
        headers=auth_header(viewer_token),
        files={"file": ("v.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert up_denied.status_code == 403

    # Format failure (.exe not allowed)
    up_failed = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("malicious.exe", b"MZ fake executable", "application/octet-stream")},
    )
    assert up_failed.status_code == 415

    # Upload success
    up_ok = client.post(
        "/documents/upload",
        headers=auth_header(owner_b_token),
        files={"file": ("ok.pdf", b"%PDF-1.4 valid", "application/pdf")},
    )
    assert up_ok.status_code == 201
    doc_id = up_ok.json()["id"]

    # 2. Downloads
    # Download denied
    dl_denied = client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token))
    assert dl_denied.status_code == 404

    # Download success by owner
    dl_ok = client.get(f"/documents/{doc_id}/download", headers=auth_header(owner_b_token))
    assert dl_ok.status_code == 200

    # 3. Document Changes
    # Edit denied for viewer
    edit_denied = client.patch(f"/documents/{doc_id}", headers=auth_header(viewer_token), json={"title": "Denied Edit"})
    assert edit_denied.status_code == 404

    # Edit failure on empty payload
    edit_fail = client.patch(f"/documents/{doc_id}", headers=auth_header(owner_b_token), json={})
    assert edit_fail.status_code == 422

    # Edit success by owner
    edit_ok = client.patch(f"/documents/{doc_id}", headers=auth_header(owner_b_token), json={"title": "Updated Title"})
    assert edit_ok.status_code == 200

    # 4. Grants & Revocations
    # Grant denied for viewer
    g_denied = client.put(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(viewer_token), json={"permission_type": "read"})
    assert g_denied.status_code == 404

    # Grant failure (non-existent user)
    g_failed = client.put(f"/documents/{doc_id}/permissions/9999999", headers=auth_header(owner_b_token), json={"permission_type": "read"})
    assert g_failed.status_code == 404

    # Grant success
    g_ok = client.put(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(owner_b_token), json={"permission_type": "read"})
    assert g_ok.status_code == 200

    # Revoke denied for viewer
    r_denied = client.delete(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(viewer_token))
    assert r_denied.status_code == 404

    # Revoke failure (no grant for non-granted user)
    r_failed = client.delete(f"/documents/{doc_id}/permissions/9999999", headers=auth_header(owner_b_token))
    assert r_failed.status_code == 404

    # Revoke success
    r_ok = client.delete(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(owner_b_token))
    assert r_ok.status_code == 204

    # 5. Deletion
    # Delete denied for viewer
    del_denied = client.delete(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert del_denied.status_code == 404

    # Delete success by owner
    del_ok = client.delete(f"/documents/{doc_id}", headers=auth_header(owner_b_token))
    assert del_ok.status_code == 204

    # 6. Verify all these records exist in audit_logs
    with SessionLocal() as db:
        # Uploads
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.action == "document_upload", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.action == "document_upload", AuditLog.outcome == "failure")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "document_upload", AuditLog.outcome == "success")) is not None

        # Downloads
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.document_id == doc_id, AuditLog.action == "document_download", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "document_download", AuditLog.outcome == "success")) is not None

        # Edits
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.document_id == doc_id, AuditLog.action == "document_edit", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "document_update", AuditLog.outcome == "failure")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "document_update", AuditLog.outcome == "success")) is not None

        # Permissions
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_grant", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_grant", AuditLog.outcome == "failure")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_grant", AuditLog.outcome == "success")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_revoke", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_revoke", AuditLog.outcome == "failure")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "permission_revoke", AuditLog.outcome == "success")) is not None

        # Deletions
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == viewer_id, AuditLog.document_id == doc_id, AuditLog.action == "document_delete", AuditLog.outcome == "denied")) is not None
        assert db.scalar(select(AuditLog).where(AuditLog.actor_id == owner_b_id, AuditLog.document_id == doc_id, AuditLog.action == "document_delete", AuditLog.outcome == "success")) is not None

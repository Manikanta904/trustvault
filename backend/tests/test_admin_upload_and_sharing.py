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
def admin_sharing_env(tmp_path, monkeypatch):
    """Set up isolated storage directory and test accounts (Admin, Owner, Viewer)."""
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    suffix = uuid4().hex
    with SessionLocal() as db:
        admin = User(
            name="Test Admin User",
            email=f"admin-{suffix}@example.com",
            password_hash=hash_password("AdminSecurePass!123"),
            role="admin",
            is_active=True,
        )
        owner = User(
            name="Test Owner User",
            email=f"owner-{suffix}@example.com",
            password_hash=hash_password("OwnerSecurePass!123"),
            role="owner",
            is_active=True,
        )
        viewer = User(
            name="Test Viewer User",
            email=f"viewer-{suffix}@example.com",
            password_hash=hash_password("ViewerSecurePass!123"),
            role="viewer",
            is_active=True,
        )
        db.add_all([admin, owner, viewer])
        db.commit()

        for u in [admin, owner, viewer]:
            db.refresh(u)

        env_data = {
            "admin": {"id": admin.id, "email": admin.email, "token": create_access_token(admin)},
            "owner": {"id": owner.id, "email": owner.email, "token": create_access_token(owner)},
            "viewer": {"id": viewer.id, "email": viewer.email, "token": create_access_token(viewer)},
            "storage_dir": tmp_path,
            "suffix": suffix,
        }

    yield env_data


def test_admin_can_upload_pdf_and_becomes_owner(admin_sharing_env):
    """Verify Admin can upload PDF and document is associated with Admin's ID as owner."""
    admin_token = admin_sharing_env["admin"]["token"]
    admin_id = admin_sharing_env["admin"]["id"]

    pdf_bytes = b"%PDF-1.4\nAdmin Uploaded Confidential Content\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(admin_token),
        files={"file": ("admin_policy.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Admin Security Policy", "category": "Compliance"},
    )

    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["title"] == "Admin Security Policy"
    assert doc_data["owner_id"] == admin_id
    assert doc_data["user_permission"] == "owner"

    doc_id = doc_data["id"]

    # Verify upload audit event was recorded with admin actor
    with SessionLocal() as db:
        upload_audit = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == admin_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "document_upload",
                AuditLog.outcome == "success",
            )
        )
        assert upload_audit is not None


def test_owner_upload_remains_functional(admin_sharing_env):
    """Verify Document Owner role can still upload PDFs."""
    owner_token = admin_sharing_env["owner"]["token"]
    owner_id = admin_sharing_env["owner"]["id"]

    pdf_bytes = b"%PDF-1.4\nOwner Document Content\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("owner_doc.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Owner Business Report", "category": "Operations"},
    )

    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["owner_id"] == owner_id
    assert doc_data["user_permission"] == "owner"


def test_viewer_upload_is_denied_and_audited(admin_sharing_env):
    """Verify Viewer role is strictly denied from uploading and denial is audited."""
    viewer_token = admin_sharing_env["viewer"]["token"]
    viewer_id = admin_sharing_env["viewer"]["id"]

    pdf_bytes = b"%PDF-1.4\nViewer Attempted Upload Content\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(viewer_token),
        files={"file": ("viewer_attempt.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Unauthorized Upload Attempt"},
    )

    assert upload_res.status_code == 403

    # Verify denial is recorded in audit log
    with SessionLocal() as db:
        denial_audit = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == viewer_id,
                AuditLog.action == "document_upload",
                AuditLog.outcome == "denied",
            )
        )
        assert denial_audit is not None


def test_admin_can_share_and_revoke_own_pdf(admin_sharing_env):
    """Verify Admin can grant and revoke read/edit permissions on Admin-owned document."""
    admin_token = admin_sharing_env["admin"]["token"]
    admin_id = admin_sharing_env["admin"]["id"]
    viewer_token = admin_sharing_env["viewer"]["token"]
    viewer_id = admin_sharing_env["viewer"]["id"]

    # 1. Admin uploads document
    pdf_bytes = b"%PDF-1.4\nAdmin PDF For Sharing\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(admin_token),
        files={"file": ("shared_admin_doc.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Admin Shared Document"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Before grant, viewer cannot access
    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 404

    # 3. Admin lists permissions for own document
    list_perm_res = client.get(f"/documents/{doc_id}/permissions", headers=auth_header(admin_token))
    assert list_perm_res.status_code == 200
    assert len(list_perm_res.json()) == 0

    # 4. Admin grants read access to viewer
    grant_res = client.put(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(admin_token),
        json={"permission_type": "read"},
    )
    assert grant_res.status_code == 200
    assert grant_res.json()["permission_type"] == "read"

    # Verify viewer now has access
    view_doc_res = client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert view_doc_res.status_code == 200
    assert view_doc_res.json()["user_permission"] == "read"

    # 5. Admin revokes access
    revoke_res = client.delete(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(admin_token),
    )
    assert revoke_res.status_code == 204

    # 6. Viewer immediately loses access
    post_revoke_res = client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token))
    assert post_revoke_res.status_code == 404

    # Verify audit logs for grant and revoke
    with SessionLocal() as db:
        grant_audit = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == admin_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "permission_grant",
                AuditLog.outcome == "success",
            )
        )
        assert grant_audit is not None

        revoke_audit = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == admin_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "permission_revoke",
                AuditLog.outcome == "success",
            )
        )
        assert revoke_audit is not None


def test_admin_bulk_sharing_and_revocation_on_own_pdf(admin_sharing_env):
    """Verify Admin can use bulk share and bulk revoke on Admin-owned document."""
    admin_token = admin_sharing_env["admin"]["token"]
    viewer_token = admin_sharing_env["viewer"]["token"]

    pdf_bytes = b"%PDF-1.4\nAdmin Bulk Sharing PDF\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(admin_token),
        files={"file": ("bulk_admin_doc.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Admin Company-Wide Memo"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Check bulk summary
    summary_res = client.get(
        f"/documents/{doc_id}/permissions/bulk-summary",
        headers=auth_header(admin_token),
    )
    assert summary_res.status_code == 200
    assert summary_res.json()["eligible_count"] >= 2  # Owner and Viewer

    # Bulk grant read
    bulk_grant_res = client.post(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(admin_token),
        json={"permission_type": "read"},
    )
    assert bulk_grant_res.status_code == 200
    assert bulk_grant_res.json()["affected_count"] >= 2

    # Viewer now has access
    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 200

    # Bulk revoke
    bulk_revoke_res = client.delete(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(admin_token),
    )
    assert bulk_revoke_res.status_code == 200
    assert bulk_revoke_res.json()["revoked_count"] >= 2

    # Viewer immediately loses access
    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_token)).status_code == 404


def test_admin_cannot_manage_another_users_private_document(admin_sharing_env):
    """
    Critical Security Constraint:
    Admin must NOT be allowed to view permission list, grant, revoke, bulk share,
    bulk revoke, or delete another user's private document solely because they are Admin.
    Admin role alone does not grant access to another user's private document.
    """
    owner_token = admin_sharing_env["owner"]["token"]
    admin_token = admin_sharing_env["admin"]["token"]
    viewer_id = admin_sharing_env["viewer"]["id"]

    # Owner uploads a private document
    pdf_bytes = b"%PDF-1.4\nOwner Strictly Private Financials\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("owner_confidential.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Owner Confidential Records"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 1. Admin cannot read metadata (returns 404)
    assert client.get(f"/documents/{doc_id}", headers=auth_header(admin_token)).status_code == 404

    # 2. Admin cannot view document stream (returns 404)
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(admin_token)).status_code == 404

    # 3. Admin cannot download document (returns 404)
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(admin_token)).status_code == 404

    # 4. Admin cannot list permissions on Owner's document (returns 404)
    assert client.get(f"/documents/{doc_id}/permissions", headers=auth_header(admin_token)).status_code == 404

    # 5. Admin cannot grant permission on Owner's document (returns 404)
    assert client.put(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(admin_token),
        json={"permission_type": "read"},
    ).status_code == 404

    # 6. Admin cannot revoke permission on Owner's document (returns 404)
    assert client.delete(
        f"/documents/{doc_id}/permissions/{viewer_id}",
        headers=auth_header(admin_token),
    ).status_code == 404

    # 7. Admin cannot access bulk summary on Owner's document (returns 404)
    assert client.get(
        f"/documents/{doc_id}/permissions/bulk-summary",
        headers=auth_header(admin_token),
    ).status_code == 404

    # 8. Admin cannot bulk grant on Owner's document (returns 404)
    assert client.post(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(admin_token),
        json={"permission_type": "read"},
    ).status_code == 404

    # 9. Admin cannot bulk revoke on Owner's document (returns 404)
    assert client.delete(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(admin_token),
    ).status_code == 404

    # 10. Admin cannot delete Owner's document (returns 404)
    assert client.delete(f"/documents/{doc_id}", headers=auth_header(admin_token)).status_code == 404

    # 11. Admin cannot view document activity history (returns 404)
    assert client.get(f"/documents/{doc_id}/activity", headers=auth_header(admin_token)).status_code == 404

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentPermission, User
from app.security import create_access_token, hash_password
import app.file_storage as file_storage
import app.routers.documents as documents_router

client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def phase2_env(tmp_path, monkeypatch):
    """Set up isolated storage directory and test accounts for Phase 2 tests."""
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    suffix = uuid4().hex
    with SessionLocal() as db:
        owner = User(
            name=f"Owner Phase2 {suffix}",
            email=f"owner-p2-{suffix}@example.com",
            password_hash=hash_password("TestPass!123456"),
            role="owner",
            is_active=True,
        )
        viewer_a = User(
            name=f"Viewer A {suffix}",
            email=f"viewer-a-{suffix}@example.com",
            password_hash=hash_password("TestPass!123456"),
            role="viewer",
            is_active=True,
        )
        viewer_b = User(
            name=f"Viewer B {suffix}",
            email=f"viewer-b-{suffix}@example.com",
            password_hash=hash_password("TestPass!123456"),
            role="viewer",
            is_active=True,
        )
        editor = User(
            name=f"Editor {suffix}",
            email=f"editor-{suffix}@example.com",
            password_hash=hash_password("TestPass!123456"),
            role="owner",
            is_active=True,
        )
        inactive = User(
            name=f"Inactive {suffix}",
            email=f"inactive-{suffix}@example.com",
            password_hash=hash_password("TestPass!123456"),
            role="viewer",
            is_active=False,
        )
        db.add_all([owner, viewer_a, viewer_b, editor, inactive])
        db.commit()

        for u in [owner, viewer_a, viewer_b, editor, inactive]:
            db.refresh(u)

        env_data = {
            "owner": {"id": owner.id, "name": owner.name, "email": owner.email, "token": create_access_token(owner)},
            "viewer_a": {"id": viewer_a.id, "name": viewer_a.name, "email": viewer_a.email, "token": create_access_token(viewer_a)},
            "viewer_b": {"id": viewer_b.id, "name": viewer_b.name, "email": viewer_b.email, "token": create_access_token(viewer_b)},
            "editor": {"id": editor.id, "name": editor.name, "email": editor.email, "token": create_access_token(editor)},
            "inactive": {"id": inactive.id, "name": inactive.name, "email": inactive.email, "token": create_access_token(inactive)},
            "suffix": suffix,
            "tmp_path": tmp_path,
        }

    yield env_data


def test_download_restricted_to_owner_viewers_and_editors_denied(phase2_env):
    """
    Phase 3 Download Policy Verification:
    1. Owner can download original file.
    2. Read recipient can download a viewer-specific watermarked copy.
    3. Edit recipient can download a viewer-specific watermarked copy.
    4. Unshared or revoked user is denied with generic 404 and audited.
    """
    owner_token = phase2_env["owner"]["token"]
    viewer_token = phase2_env["viewer_a"]["token"]
    viewer_id = phase2_env["viewer_a"]["id"]
    unshared_token = phase2_env["viewer_b"]["token"]
    unshared_id = phase2_env["viewer_b"]["id"]
    editor_token = phase2_env["editor"]["token"]
    editor_id = phase2_env["editor"]["id"]

    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "Confidential Financial Data")
    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("financial.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Q4 Financials"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Grant read to viewer_a, grant edit to editor
    client.put(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(owner_token), json={"permission_type": "read"})
    client.put(f"/documents/{doc_id}/permissions/{editor_id}", headers=auth_header(owner_token), json={"permission_type": "edit"})

    # 1. Owner can download original file
    owner_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(owner_token))
    assert owner_dl.status_code == 200
    assert owner_dl.content == pdf_bytes
    assert "attachment" in owner_dl.headers.get("content-disposition", "")

    # 2. Viewer with read downloads a watermarked copy
    viewer_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(viewer_token))
    assert viewer_dl.status_code == 200
    assert viewer_dl.content != pdf_bytes
    assert "attachment" in viewer_dl.headers.get("content-disposition", "")

    # 3. Editor with edit downloads a watermarked copy
    editor_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(editor_token))
    assert editor_dl.status_code == 200
    assert editor_dl.content != pdf_bytes
    assert "attachment" in editor_dl.headers.get("content-disposition", "")

    # 4. Unshared user cannot download (404)
    unshared_dl = client.get(f"/documents/{doc_id}/download", headers=auth_header(unshared_token))
    assert unshared_dl.status_code == 404

    # 5. Both viewer and editor can view in-browser
    v_view = client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_token))
    assert v_view.status_code == 200
    assert v_view.content == pdf_bytes

    e_view = client.get(f"/documents/{doc_id}/view", headers=auth_header(editor_token))
    assert e_view.status_code == 200
    assert e_view.content == pdf_bytes

    # 6. Verify audit logs
    with SessionLocal() as db:
        unshared_audit = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == unshared_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "document_download",
                AuditLog.outcome == "denied",
            )
        )
        assert unshared_audit is not None


def test_secure_view_endpoint_headers_and_security(phase2_env):
    """
    Requirement B Verification:
    - Returns content_disposition inline.
    - Sets Cache-Control: private, no-store, must-revalidate.
    - Sets anti-framing / CSP headers.
    - Audits successful view and denied attempts.
    """
    owner_token = phase2_env["owner"]["token"]
    viewer_token = phase2_env["viewer_a"]["token"]
    viewer_id = phase2_env["viewer_a"]["id"]

    pdf_bytes = b"%PDF-1.4\nSecure View Specimen\n%%EOF"
    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("view_test.pdf", pdf_bytes, "application/pdf")},
        data={"title": "View Security Test"},
    )
    doc_id = upload_res.json()["id"]

    # Unshared viewer cannot view (404)
    denied_view = client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_token))
    assert denied_view.status_code == 404

    # Grant read
    client.put(f"/documents/{doc_id}/permissions/{viewer_id}", headers=auth_header(owner_token), json={"permission_type": "read"})

    # Authorized view
    view_res = client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_token))
    assert view_res.status_code == 200
    assert view_res.content == pdf_bytes
    assert "inline" in view_res.headers.get("content-disposition", "")
    assert "private" in view_res.headers.get("cache-control", "")
    assert "no-store" in view_res.headers.get("cache-control", "")
    assert view_res.headers.get("x-content-type-options") == "nosniff"
    assert view_res.headers.get("x-frame-options") == "SAMEORIGIN"

    # Verify audit logs
    with SessionLocal() as db:
        view_log = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == viewer_id,
                AuditLog.document_id == doc_id,
                AuditLog.action == "document_view",
                AuditLog.outcome == "success",
            )
        )
        assert view_log is not None


def test_bulk_sharing_lifecycle_and_summary(phase2_env):
    """
    Requirements C, D, E Verification:
    1. Pre-flight summary returns eligible count and excludes owner/inactive accounts.
    2. Non-owner cannot invoke bulk summary or bulk sharing.
    3. Bulk grant shares document with all active employees in an atomic transaction.
    4. Individual grants are created with correct granted_by attribution.
    5. Upgrading from read to edit works.
    6. Bulk revoke removes all grants atomically.
    7. Future view/metadata requests immediately return 404 after bulk revoke.
    """
    owner_token = phase2_env["owner"]["token"]
    owner_id = phase2_env["owner"]["id"]
    viewer_a_token = phase2_env["viewer_a"]["token"]
    viewer_a_id = phase2_env["viewer_a"]["id"]
    viewer_b_token = phase2_env["viewer_b"]["token"]
    viewer_b_id = phase2_env["viewer_b"]["id"]
    editor_token = phase2_env["editor"]["token"]
    inactive_id = phase2_env["inactive"]["id"]

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("company_policy.pdf", b"%PDF-1.4 Company Policy", "application/pdf")},
        data={"title": "Company Wide Policy"},
    )
    doc_id = upload_res.json()["id"]

    # 1. Non-owner cannot call bulk-summary (404)
    assert client.get(f"/documents/{doc_id}/permissions/bulk-summary", headers=auth_header(viewer_a_token)).status_code == 404

    # 2. Owner calls bulk-summary
    summary_res = client.get(f"/documents/{doc_id}/permissions/bulk-summary", headers=auth_header(owner_token))
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["document_id"] == doc_id
    assert summary["eligible_count"] >= 3  # at least viewer_a, viewer_b, editor
    assert summary["new_grant_count"] == summary["eligible_count"]
    assert summary["existing_grant_count"] == 0

    # 3. Non-owner cannot call bulk grant (404)
    assert client.post(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(viewer_a_token),
        json={"permission_type": "read"},
    ).status_code == 404

    # 4. Owner executes bulk sharing with 'read'
    bulk_res = client.post(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(owner_token),
        json={"permission_type": "read"},
    )
    assert bulk_res.status_code == 200
    assert bulk_res.json()["document_id"] == doc_id
    assert bulk_res.json()["permission_type"] == "read"
    assert bulk_res.json()["affected_count"] == summary["eligible_count"]

    # 5. Verify individual records in database
    with SessionLocal() as db:
        perms = db.scalars(
            select(DocumentPermission).where(DocumentPermission.document_id == doc_id)
        ).all()
        perm_users = {p.user_id: (p.permission_type, p.granted_by) for p in perms}

        # Active users received grants
        assert viewer_a_id in perm_users
        assert viewer_b_id in perm_users
        assert perm_users[viewer_a_id] == ("read", owner_id)
        assert perm_users[viewer_b_id] == ("read", owner_id)

        # Inactive user and owner were NOT granted
        assert inactive_id not in perm_users
        assert owner_id not in perm_users

    # 6. Verify recipients can now view document
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_a_token)).status_code == 200
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_b_token)).status_code == 200

    # 7. Summary now reflects existing grants
    summary2 = client.get(f"/documents/{doc_id}/permissions/bulk-summary", headers=auth_header(owner_token)).json()
    assert summary2["new_grant_count"] == 0
    assert summary2["existing_grant_count"] == summary["eligible_count"]

    # 8. Upgrade bulk permissions to 'edit'
    upgrade_res = client.post(
        f"/documents/{doc_id}/permissions/bulk",
        headers=auth_header(owner_token),
        json={"permission_type": "edit"},
    )
    assert upgrade_res.status_code == 200
    assert upgrade_res.json()["permission_type"] == "edit"

    with SessionLocal() as db:
        p_check = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == doc_id,
                DocumentPermission.user_id == viewer_a_id,
            )
        )
        assert p_check.permission_type == "edit"

    # 9. Non-owner cannot call bulk revoke
    assert client.delete(f"/documents/{doc_id}/permissions/bulk", headers=auth_header(viewer_a_token)).status_code == 404

    # 10. Owner executes bulk revoke
    revoke_res = client.delete(f"/documents/{doc_id}/permissions/bulk", headers=auth_header(owner_token))
    assert revoke_res.status_code == 200
    assert revoke_res.json()["revoked_count"] >= 3

    # 11. Immediate revocation: recipients now receive 404 on view and metadata
    assert client.get(f"/documents/{doc_id}", headers=auth_header(viewer_a_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_a_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(viewer_b_token)).status_code == 404


def test_bulk_grant_transaction_rollback_on_failure(phase2_env, monkeypatch):
    """
    Requirement 11 Verification:
    Verify atomic rollback: if an exception occurs mid-operation during bulk grant,
    the entire transaction is rolled back and zero partial grants remain.
    """
    owner_token = phase2_env["owner"]["token"]

    upload_res = client.post(
        "/documents/upload",
        headers=auth_header(owner_token),
        files={"file": ("rollback_test.pdf", b"%PDF-1.4 Test", "application/pdf")},
    )
    doc_id = upload_res.json()["id"]

    # Verify no permissions exist initially
    with SessionLocal() as db:
        initial_count = db.scalar(
            select(DocumentPermission).where(DocumentPermission.document_id == doc_id)
        )
        assert initial_count is None

    # Simulate database error during audit recording inside bulk grant
    original_record_audit = documents_router.record_audit
    def failing_record_audit(db, actor, action, outcome, **kwargs):
        if action == "permission_bulk_grant" and outcome == "success":
            raise RuntimeError("Simulated mid-transaction failure")
        return original_record_audit(db, actor, action=action, outcome=outcome, **kwargs)

    monkeypatch.setattr(documents_router, "record_audit", failing_record_audit)

    # Attempt bulk grant; must fail
    with pytest.raises(RuntimeError, match="Simulated mid-transaction failure"):
        client.post(
            f"/documents/{doc_id}/permissions/bulk",
            headers=auth_header(owner_token),
            json={"permission_type": "read"},
        )

    # Verify atomic rollback: NO grants were committed
    with SessionLocal() as db:
        perms_after = list(
            db.scalars(
                select(DocumentPermission).where(DocumentPermission.document_id == doc_id)
            ).all()
        )
        assert len(perms_after) == 0, f"Expected 0 partial grants after rollback, found {len(perms_after)}"

        # Failure was audited
        failure_log = db.scalar(
            select(AuditLog).where(
                AuditLog.document_id == doc_id,
                AuditLog.action == "permission_bulk_grant",
                AuditLog.outcome == "failure",
            )
        )
        assert failure_log is not None

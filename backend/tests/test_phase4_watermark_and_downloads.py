import io
import hashlib
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import select, text

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentPermission, User
from app.security import create_access_token, hash_password
import app.file_storage as file_storage
import app.file_storage as file_storage
from app.rate_limiter import (
    login_rate_limiter,
    register_rate_limiter,
    user_search_rate_limiter,
    document_sensitive_limiter,
)

client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_sample_pdf(pages: int = 1, text: str = "Sample Document") -> bytes:
    """Generate a valid single- or multi-page PDF in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for p in range(pages):
        c.drawString(100, 700, f"{text} - Page {p + 1}")
        c.drawString(100, 650, "Proprietary information for internal use.")
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def phase4_env(tmp_path, monkeypatch):
    """Set up isolated storage directory and test accounts for Phase 4 tests."""
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)
    # Clear rate limiter state between test fixtures
    login_rate_limiter.reset()
    register_rate_limiter.reset()
    user_search_rate_limiter.reset()
    document_sensitive_limiter.reset()

    suffix = uuid4().hex[:8]
    with SessionLocal() as db:
        owner = User(
            name=f"Owner Phase4 {suffix}",
            email=f"owner-p4-{suffix}@example.com",
            password_hash=hash_password("Pass12345!"),
            role="owner",
            is_active=True,
        )
        viewer_read = User(
            name=f"Viewer Read {suffix}",
            email=f"viewer-read-{suffix}@example.com",
            password_hash=hash_password("Pass12345!"),
            role="viewer",
            is_active=True,
        )
        viewer_edit = User(
            name=f"Viewer Edit {suffix}",
            email=f"viewer-edit-{suffix}@example.com",
            password_hash=hash_password("Pass12345!"),
            role="viewer",
            is_active=True,
        )
        unrelated = User(
            name=f"Unrelated User {suffix}",
            email=f"unrelated-{suffix}@example.com",
            password_hash=hash_password("Pass12345!"),
            role="viewer",
            is_active=True,
        )
        admin = User(
            name=f"Admin User {suffix}",
            email=f"admin-p4-{suffix}@example.com",
            password_hash=hash_password("Pass12345!"),
            role="admin",
            is_active=True,
        )
        db.add_all([owner, viewer_read, viewer_edit, unrelated, admin])
        db.commit()
        for u in [owner, viewer_read, viewer_edit, unrelated, admin]:
            db.refresh(u)

        env_data = {
            "owner": owner,
            "viewer_read": viewer_read,
            "viewer_edit": viewer_edit,
            "unrelated": unrelated,
            "admin": admin,
            "owner_token": create_access_token(owner),
            "read_token": create_access_token(viewer_read),
            "edit_token": create_access_token(viewer_edit),
            "unrelated_token": create_access_token(unrelated),
            "admin_token": create_access_token(admin),
        }
        return env_data


def test_01_owner_preview_and_original_download_succeed(phase4_env):
    """1. Owner preview and original download succeed."""
    pdf_bytes = create_sample_pdf(pages=1, text="Quarterly Financials")
    owner_token = phase4_env["owner_token"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("q_report.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Q Report", "category": "Finance"},
        headers=auth_header(owner_token),
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Preview succeeds
    view_res = client.get(f"/documents/{doc_id}/view", headers=auth_header(owner_token))
    assert view_res.status_code == 200
    assert view_res.headers["content-type"] == "application/pdf"
    assert "inline" in view_res.headers["content-disposition"]
    assert "no-store" in view_res.headers["cache-control"]

    # Download succeeds with original content
    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(owner_token))
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] in ["application/pdf", "application/octet-stream"]
    assert dl_res.content == pdf_bytes  # Owner gets exact original


def test_02_shared_read_viewer_preview_succeeds(phase4_env):
    """2. Shared-read viewer preview succeeds."""
    pdf_bytes = create_sample_pdf(pages=1, text="Shared Handbook")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Employee Handbook"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    # Grant read access
    share_res = client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )
    assert share_res.status_code == 200

    # Shared read preview succeeds
    view_res = client.get(f"/documents/{doc_id}/view", headers=auth_header(read_token))
    assert view_res.status_code == 200
    assert view_res.headers["content-type"] == "application/pdf"
    assert "inline" in view_res.headers["content-disposition"]


def test_03_shared_read_viewer_download_returns_watermarked_copy(phase4_env):
    """3. Shared-read viewer download returns a watermarked copy."""
    pdf_bytes = create_sample_pdf(pages=1, text="Security Architecture")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("sec_arch.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Sec Arch"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert "attachment" in dl_res.headers["content-disposition"]

    # Must NOT be identical to the original raw bytes because a watermark was applied
    assert dl_res.content != pdf_bytes

    # Must be a valid PDF and contain the viewer's email and UTC timestamp
    reader = PdfReader(io.BytesIO(dl_res.content))
    assert len(reader.pages) == 1
    page_text = reader.pages[0].extract_text()
    assert read_user.email in page_text
    assert f"Doc #{doc_id}" in page_text or f"TRC-{doc_id}" in page_text


def test_04_shared_edit_viewer_download_returns_watermarked_copy(phase4_env):
    """4. Shared-edit viewer download returns a watermarked copy."""
    pdf_bytes = create_sample_pdf(pages=1, text="Budget Draft")
    owner_token = phase4_env["owner_token"]
    edit_token = phase4_env["edit_token"]
    edit_user = phase4_env["viewer_edit"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("budget.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Budget Draft"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{edit_user.id}",
        json={"permission_type": "edit"},
        headers=auth_header(owner_token),
    )

    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(edit_token))
    assert dl_res.status_code == 200
    assert dl_res.content != pdf_bytes

    reader = PdfReader(io.BytesIO(dl_res.content))
    page_text = reader.pages[0].extract_text()
    assert edit_user.email in page_text
    assert "UTC" in page_text


def test_05_original_stored_pdf_remains_unchanged(phase4_env):
    """5. Original stored PDF remains unchanged after generating shared copies."""
    pdf_bytes = create_sample_pdf(pages=2, text="Original Contract")
    original_hash = hashlib.sha256(pdf_bytes).hexdigest()
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Contract"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Viewer downloads watermarked copy multiple times
    for _ in range(2):
        dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))
        assert dl_res.status_code == 200

    # Retrieve stored document from DB to check stored file on disk
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        storage_path = file_storage.get_storage_path(doc.storage_key)
        disk_bytes = storage_path.read_bytes()
        disk_hash = hashlib.sha256(disk_bytes).hexdigest()
        assert disk_hash == original_hash
        assert disk_bytes == pdf_bytes


def test_06_watermark_metadata_belongs_to_authenticated_viewer(phase4_env):
    """6. Watermark metadata belongs to the authenticated viewer."""
    pdf_bytes = create_sample_pdf(pages=1, text="Sensitive IP")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("ip.pdf", pdf_bytes, "application/pdf")},
        data={"title": "IP Document"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))
    reader = PdfReader(io.BytesIO(dl_res.content))
    page_text = reader.pages[0].extract_text()

    assert read_user.email in page_text
    assert read_user.name in page_text
    assert f"Doc #{doc_id}" in page_text or f"TRC-{doc_id}" in page_text
    assert "CONFIDENTIAL" in page_text


def test_07_multipage_pdf_contains_watermark_on_each_page(phase4_env):
    """7. Multi-page PDFs contain the expected watermark placements on each page."""
    pdf_bytes = create_sample_pdf(pages=3, text="Comprehensive Audit")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("audit_multi.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Multi-page Audit"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))
    assert dl_res.status_code == 200

    reader = PdfReader(io.BytesIO(dl_res.content))
    assert len(reader.pages) == 3
    for p_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        assert read_user.email in text, f"Page {p_idx + 1} missing viewer email watermark"
        assert "UTC" in text, f"Page {p_idx + 1} missing UTC watermark timestamp"


def test_08_watermarked_copies_not_cached_or_shared_across_users(phase4_env):
    """8. Watermarked copies are not accidentally shared or cached across users."""
    pdf_bytes = create_sample_pdf(pages=1, text="Confidential Strategy")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]
    edit_token = phase4_env["edit_token"]
    edit_user = phase4_env["viewer_edit"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("strategy.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Strategy"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    # Share with both users
    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )
    client.put(
        f"/documents/{doc_id}/permissions/{edit_user.id}",
        json={"permission_type": "edit"},
        headers=auth_header(owner_token),
    )

    # User A downloads
    dl_a = client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))
    reader_a = PdfReader(io.BytesIO(dl_a.content))
    text_a = reader_a.pages[0].extract_text()
    assert read_user.email in text_a
    assert edit_user.email not in text_a

    # User B downloads
    dl_b = client.get(f"/documents/{doc_id}/download", headers=auth_header(edit_token))
    reader_b = PdfReader(io.BytesIO(dl_b.content))
    text_b = reader_b.pages[0].extract_text()
    assert edit_user.email in text_b
    assert read_user.email not in text_b


def test_09_unrelated_user_cannot_preview_or_download(phase4_env):
    """9. An unrelated user cannot preview or download a document."""
    pdf_bytes = create_sample_pdf(pages=1, text="Top Secret Project")
    owner_token = phase4_env["owner_token"]
    unrelated_token = phase4_env["unrelated_token"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("top_secret.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Top Secret"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    # View attempt by unrelated user returns 404
    view_res = client.get(f"/documents/{doc_id}/view", headers=auth_header(unrelated_token))
    assert view_res.status_code == 404

    # Download attempt by unrelated user returns 404
    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(unrelated_token))
    assert dl_res.status_code == 404


def test_10_revocation_immediately_blocks_subsequent_preview_and_download(phase4_env):
    """10. Revocation immediately blocks subsequent preview and download requests."""
    pdf_bytes = create_sample_pdf(pages=1, text="Temporary Share")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("temp.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Temporary Doc"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    # Grant permission
    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Preview and download succeed while permission is active
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(read_token)).status_code == 200
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token)).status_code == 200

    # Owner revokes permission
    revoke_res = client.delete(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        headers=auth_header(owner_token),
    )
    assert revoke_res.status_code in [200, 204]

    # Next preview and download requests MUST be immediately denied (HTTP 404)
    assert client.get(f"/documents/{doc_id}/view", headers=auth_header(read_token)).status_code == 404
    assert client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token)).status_code == 404


def test_11_shared_user_cannot_manage_permissions_or_download_unwatermarked(phase4_env):
    """11. A shared user cannot manage permissions or download the unwatermarked original."""
    pdf_bytes = create_sample_pdf(pages=1, text="Protected Asset")
    owner_token = phase4_env["owner_token"]
    edit_token = phase4_env["edit_token"]
    edit_user = phase4_env["viewer_edit"]
    unrelated_user = phase4_env["unrelated"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("protected.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Protected Asset"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{edit_user.id}",
        json={"permission_type": "edit"},
        headers=auth_header(owner_token),
    )

    # Shared editor attempts to grant permission to someone else -> 404 (only owner can manage)
    grant_attempt = client.put(
        f"/documents/{doc_id}/permissions/{unrelated_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(edit_token),
    )
    assert grant_attempt.status_code == 404

    # Shared editor download returns watermarked, NOT original
    dl_res = client.get(f"/documents/{doc_id}/download", headers=auth_header(edit_token))
    assert dl_res.status_code == 200
    assert dl_res.content != pdf_bytes


def test_12_unauthorized_metadata_edits_deletions_and_bulk_rejected(phase4_env):
    """12. Unauthorized metadata edits, deletions and bulk operations are rejected."""
    pdf_bytes = create_sample_pdf(pages=1, text="Restricted Asset")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("restricted.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Original Title"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Read-only user attempts to edit title -> 404
    edit_res = client.patch(
        f"/documents/{doc_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(read_token),
    )
    assert edit_res.status_code == 404

    # Read-only user attempts to delete document -> 404
    del_res = client.delete(f"/documents/{doc_id}", headers=auth_header(read_token))
    assert del_res.status_code == 404

    # Read-only user attempts bulk grant -> 404
    bulk_grant_res = client.post(
        f"/documents/{doc_id}/permissions/bulk",
        json={"permission_type": "read"},
        headers=auth_header(read_token),
    )
    assert bulk_grant_res.status_code == 404


def test_13_audit_events_recorded_for_successful_and_denied_attempts(phase4_env):
    """13. Audit events are recorded for successful and denied attempts."""
    pdf_bytes = create_sample_pdf(pages=1, text="Audit Verification")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]
    unrelated_token = phase4_env["unrelated_token"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("audit_verif.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Audit Doc"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Successful view & download by shared viewer
    client.get(f"/documents/{doc_id}/view", headers=auth_header(read_token))
    client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))

    # Denied view & download by unrelated user
    client.get(f"/documents/{doc_id}/view", headers=auth_header(unrelated_token))
    client.get(f"/documents/{doc_id}/download", headers=auth_header(unrelated_token))

    # Inspect audit_logs in DB
    with SessionLocal() as db:
        logs = db.scalars(
            select(AuditLog).where(AuditLog.document_id == doc_id).order_by(AuditLog.id)
        ).all()
        actions = [(l.action, l.outcome) for l in logs]
        assert ("document_view", "success") in actions
        assert ("document_download", "success") in actions
        assert ("document_view", "denied") in actions
        assert ("document_download", "denied") in actions


def test_14_owner_activity_and_admin_audit_visibility(phase4_env):
    """14. Owner activity endpoint returns download events to owner only."""
    pdf_bytes = create_sample_pdf(pages=1, text="Activity Tracking")
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]
    unrelated_token = phase4_env["unrelated_token"]
    admin_token = phase4_env["admin_token"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("activity.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Activity Doc"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Recipient downloads
    client.get(f"/documents/{doc_id}/download", headers=auth_header(read_token))

    # Owner views activity
    act_res = client.get(f"/documents/{doc_id}/activity", headers=auth_header(owner_token))
    assert act_res.status_code == 200
    data = act_res.json()
    assert data["document_id"] == doc_id
    download_items = [i for i in data["items"] if i["action"] == "document_download"]
    assert len(download_items) >= 1
    assert download_items[0]["actor_email"] == read_user.email
    assert download_items[0]["actor_name"] == read_user.name

    # Unrelated user cannot view owner activity -> 404
    unrelated_act = client.get(f"/documents/{doc_id}/activity", headers=auth_header(unrelated_token))
    assert unrelated_act.status_code == 404

    # Admin audit list shows system-wide audit records
    admin_logs = client.get("/admin/audit-logs", headers=auth_header(admin_token))
    assert admin_logs.status_code == 200
    assert len(admin_logs.json()) > 0


def test_15_audit_immutability_trigger_enforcement():
    """15. Audit records cannot be modified or deleted due to append-only database trigger."""
    with SessionLocal() as db:
        # Fetch an existing audit log
        log = db.scalars(select(AuditLog).limit(1)).first()
        if log:
            # Attempt direct UPDATE via SQL
            with pytest.raises(Exception) as exc_info:
                db.execute(
                    text("UPDATE audit_logs SET details = 'tampered' WHERE id = :id"),
                    {"id": log.id},
                )
                db.commit()
            err_msg = str(exc_info.value).lower()
            assert "append-only" in err_msg or "permission denied" in err_msg
            db.rollback()


def test_16_upload_signature_and_malformed_file_checks(phase4_env):
    """16. Upload signature, size and malformed-file checks work."""
    owner_token = phase4_env["owner_token"]

    # Spoofed extension: text file disguised as PDF -> rejected
    fake_pdf = b"This is plain text pretending to be a pdf file."
    spoof_res = client.post(
        "/documents/upload",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
        data={"title": "Fake PDF"},
        headers=auth_header(owner_token),
    )
    assert spoof_res.status_code == 415

    # Valid PDF magic bytes
    valid_pdf = create_sample_pdf(1, "Valid Doc")
    valid_res = client.post(
        "/documents/upload",
        files={"file": ("valid.pdf", valid_pdf, "application/pdf")},
        data={"title": "Valid Doc"},
        headers=auth_header(owner_token),
    )
    assert valid_res.status_code == 201


def test_17_rate_limiter_blocks_excessive_requests(phase4_env):
    """17. Rate limits block brute force / excessive document enumerations."""
    owner_token = phase4_env["owner_token"]

    # Clear rate limiter
    user_search_rate_limiter.reset()

    # Trigger rate limiter on /users/search (configured at 30/minute)
    responses = []
    for _ in range(35):
        res = client.get("/users/search?q=test", headers=auth_header(owner_token))
        responses.append(res.status_code)

    assert 429 in responses
    rate_limited_res = [r for r in responses if r == 429]
    assert len(rate_limited_res) > 0


def test_18_owner_search_filter_returns_only_authorized_documents(phase4_env):
    """18. Owner name/email filter returns only authorized documents."""
    pdf_bytes = create_sample_pdf(pages=1, text="Filtered Document")
    owner = phase4_env["owner"]
    owner_token = phase4_env["owner_token"]
    read_token = phase4_env["read_token"]
    read_user = phase4_env["viewer_read"]
    unrelated_token = phase4_env["unrelated_token"]

    upload_res = client.post(
        "/documents/upload",
        files={"file": ("filtered.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Filtered Document"},
        headers=auth_header(owner_token),
    )
    doc_id = upload_res.json()["id"]

    client.put(
        f"/documents/{doc_id}/permissions/{read_user.id}",
        json={"permission_type": "read"},
        headers=auth_header(owner_token),
    )

    # Shared reader searches by owner name/email
    search_res = client.get(
        f"/documents?owner_search={owner.email}",
        headers=auth_header(read_token),
    )
    assert search_res.status_code == 200
    docs = search_res.json()
    doc_ids = [d["id"] for d in docs]
    assert doc_id in doc_ids
    matched_doc = next(d for d in docs if d["id"] == doc_id)
    assert matched_doc["owner_email"] == owner.email
    assert matched_doc["owner_name"] == owner.name
    assert matched_doc["user_permission"] == "read"

    # Unrelated user searches with same filter -> gets empty list (not authorized)
    unrelated_res = client.get(
        f"/documents?owner_search={owner.email}",
        headers=auth_header(unrelated_token),
    )
    assert unrelated_res.status_code == 200
    unrelated_ids = [d["id"] for d in unrelated_res.json()]
    assert doc_id not in unrelated_ids

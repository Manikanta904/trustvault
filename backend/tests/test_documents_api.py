
from uuid import uuid4
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentPermission, User
from app.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture
def test_accounts():
    suffix = uuid4().hex
    emails = [
        f"api-owner-{suffix}@example.com",
        f"api-viewer-{suffix}@example.com",
    ]

    with SessionLocal() as db:
        owner = User(
            name="API Test Owner",
            email=emails[0],
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        viewer = User(
            name="API Test Viewer",
            email=emails[1],
            password_hash=hash_password("TestOnly!Password123"),
            role="viewer",
            is_active=True,
        )
        db.add_all([owner, viewer])
        db.commit()
        db.refresh(owner)
        db.refresh(viewer)

        owner_id = owner.id
        viewer_id = viewer.id
        owner_token = create_access_token(owner)
        viewer_token = create_access_token(viewer)

    yield {
        "owner_id": owner_id,
        "viewer_id": viewer_id,
        "owner_token": owner_token,
        "viewer_token": viewer_token,
        "emails": emails,
    }


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_document(token, title, filename, category="Testing"):
    """Create document metadata through the API."""
    response = client.post(
        "/documents",
        headers=auth(token),
        json={
            "title": title,
            "description": "Automated test document",
            "category": category,
            "original_filename": filename,
            "content_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_document_endpoints_require_authentication():
    assert client.get("/documents").status_code == 401

    response = client.post(
        "/documents",
        json={
            "title": "Unauthenticated",
            "original_filename": "test.pdf",
            "size_bytes": 0,
        },
    )
    assert response.status_code == 401


def test_owner_can_create_and_read_document(test_accounts):
    token = test_accounts["owner_token"]

    created = create_document(
        token,
        "Integration Test Document",
        "example.pdf",
    )
    document_id = created["id"]

    assert created["owner_id"] == test_accounts["owner_id"]
    assert "storage_key" not in created

    response = client.get(
        f"/documents/{document_id}",
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == document_id


def test_document_update_is_not_saved_when_audit_write_fails(
    test_accounts, monkeypatch
):
    import app.routers.documents as documents_router

    document = create_document(
        test_accounts["owner_token"],
        "Original Audit Test Title",
        "audit-test.pdf",
    )
    document_id = document["id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit database failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)

    test_client = TestClient(app, raise_server_exceptions=False)
    response = test_client.patch(
        f"/documents/{document_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"title": "This update must not persist"},
    )

    assert response.status_code == 500

    # Check the database directly, without triggering another audit event.
    with SessionLocal() as db:
        saved_document = db.get(Document, document_id)
        assert saved_document is not None
        assert saved_document.title == "Original Audit Test Title"


def test_ungranted_user_cannot_read_edit_or_delete(test_accounts):
    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]

    document = create_document(
        owner_token,
        "Private Integration Test",
        "private.pdf",
    )
    document_id = document["id"]

    response = client.get(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    response = client.patch(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
        json={"title": "Unauthorized change"},
    )
    assert response.status_code == 404

    response = client.delete(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    with SessionLocal() as db:
        denied_logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_id == test_accounts["viewer_id"],
                    AuditLog.document_id == document_id,
                    AuditLog.outcome == "denied",
                )
            ).all()
        )

    assert len(denied_logs) >= 3


def test_read_grant_denies_edit_but_edit_grant_allows_it(test_accounts):
    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]
    viewer_id = test_accounts["viewer_id"]

    document = create_document(
        owner_token,
        "Permission Level Test",
        "permission-level-test.pdf",
    )
    document_id = document["id"]

    # Grant read-only permission.
    response = client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 200, response.text

    # Read-only users can access metadata.
    response = client.get(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200, response.text

    # Read-only users cannot edit.
    response = client.patch(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
        json={"title": "Read-only user attempted edit"},
    )
    assert response.status_code == 404

    # Upgrade the same user's permission to edit.
    response = client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
        json={"permission_type": "edit"},
    )
    assert response.status_code == 200, response.text

    # Edit permission allows metadata changes.
    response = client.patch(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
        json={"title": "Edited by viewer"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Edited by viewer"

    # Edit permission must not allow document deletion.
    response = client.delete(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404


def test_viewer_cannot_create_document_metadata(test_accounts):
    response = client.post(
        "/documents",
        headers=auth(test_accounts["viewer_token"]),
        json={
            "title": "Viewer-created document",
            "original_filename": "test.pdf",
            "content_type": "application/pdf",
            "size_bytes": 0,
        },
    )

    assert response.status_code == 403


def test_upload_download_grant_and_revoke(
    test_accounts, tmp_path, monkeypatch
):
    import app.file_storage as file_storage

    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]
    viewer_id = test_accounts["viewer_id"]

    import io
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "Private PDF Specimen")
    c.showPage()
    c.save()
    pdf_content = buf.getvalue()

    response = client.post(
        "/documents/upload",
        headers=auth(owner_token),
        files={
            "file": ("sample.pdf", pdf_content, "application/pdf")
        },
        data={"title": "Private PDF", "category": "Testing"},
    )

    assert response.status_code == 201, response.text
    document = response.json()
    document_id = document["id"]

    assert "storage_key" not in document
    assert len(list(tmp_path.iterdir())) == 1

    # Before grant: unshared recipient is blocked with 404
    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    response = client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 200, response.text

    # Recipient with read permission can view in-browser via /view
    view_response = client.get(
        f"/documents/{document_id}/view",
        headers=auth(viewer_token),
    )
    assert view_response.status_code == 200
    assert view_response.content == pdf_content
    assert "inline" in view_response.headers.get("content-disposition", "")

    # Shared read recipient receives a viewer-specific watermarked copy
    viewer_dl = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert viewer_dl.status_code == 200
    assert "attachment" in viewer_dl.headers.get("content-disposition", "")
    assert viewer_dl.content != pdf_content

    # Document owner downloads the original file
    owner_dl = client.get(
        f"/documents/{document_id}/download",
        headers=auth(owner_token),
    )
    assert owner_dl.status_code == 200
    assert owner_dl.content == pdf_content

    # Revoke access
    response = client.delete(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
    )
    assert response.status_code == 204

    # Verify the viewer cannot access metadata, download, or view after revocation.
    assert client.get(f"/documents/{document_id}", headers=auth(viewer_token)).status_code == 404
    assert client.get(f"/documents/{document_id}/download", headers=auth(viewer_token)).status_code == 404
    assert client.get(f"/documents/{document_id}/view", headers=auth(viewer_token)).status_code == 404

    download_after_revoke = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert download_after_revoke.status_code == 404

    # Revoked documents must disappear from the viewer's list.
    list_after_revoke = client.get(
        "/documents",
        headers=auth(viewer_token),
    )
    assert list_after_revoke.status_code == 200
    assert document_id not in {
        item["id"] for item in list_after_revoke.json()
    }

    # Searching must not reveal the revoked document.
    search_after_revoke = client.get(
        "/documents",
        params={"search": "Private PDF"},
        headers=auth(viewer_token),
    )
    assert search_after_revoke.status_code == 200
    assert document_id not in {
        item["id"] for item in search_after_revoke.json()
    }

    # A viewer whose access was revoked must not edit metadata.
    edit_after_revoke = client.patch(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
        json={"title": "Unauthorized edit"},
    )
    assert edit_after_revoke.status_code == 404

    # Revocation must not allow the viewer to delete the document.
    delete_after_revoke = client.delete(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert delete_after_revoke.status_code == 404

    # Revoking access must not delete the owner's stored file.
    assert len(list(tmp_path.iterdir())) == 1

    with SessionLocal() as db:
        denied = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_id == viewer_id,
                    AuditLog.document_id == document_id,
                    AuditLog.action == "document_read",
                    AuditLog.outcome == "denied",
                )
            ).all()
        )

    assert denied


def test_failed_upload_is_recorded_in_audit_log(
    test_accounts, tmp_path, monkeypatch
):
    import app.file_storage as file_storage

    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    response = client.post(
        "/documents/upload",
        headers=auth(test_accounts["owner_token"]),
        files={
            "file": (
                "malicious.exe",
                b"not an allowed document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code in (400, 415, 422), response.text

    with SessionLocal() as db:
        failure_logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_id == test_accounts["owner_id"],
                    AuditLog.action == "document_upload",
                    AuditLog.outcome == "failure",
                )
            ).all()
        )

    assert failure_logs, "Failed upload was not recorded in the audit log"



def test_upload_commit_failure_cleans_up_file_and_database(
    test_accounts, tmp_path, monkeypatch
):
    import app.file_storage as file_storage
    import app.routers.documents as documents_router

    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit write failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)

    test_client = TestClient(app, raise_server_exceptions=False)

    response = test_client.post(
        "/documents/upload",
        headers=auth(test_accounts["owner_token"]),
        files={
            "file": (
                "rollback-test.pdf",
                b"%PDF-1.4\n%%EOF\n",
                "application/pdf",
            )
        },
        data={"title": "Rollback Test", "category": "Testing"},
    )

    assert response.status_code == 500
    assert list(tmp_path.iterdir()) == []

    with SessionLocal() as db:
        document = db.scalar(
            select(Document).where(
                Document.owner_id == test_accounts["owner_id"],
                Document.title == "Rollback Test",
            )
        )
        assert document is None


def test_delete_document_keeps_audit_record(test_accounts):
    owner_token = test_accounts["owner_token"]
    owner_id = test_accounts["owner_id"]

    document = create_document(
        owner_token,
        "Document Deletion Audit Test",
        "deletion-audit-test.pdf",
    )
    document_id = document["id"]

    response = client.delete(
        f"/documents/{document_id}",
        headers=auth(owner_token),
    )

    assert response.status_code == 204, response.text

    with SessionLocal() as db:
        # The document itself should no longer exist.
        assert db.get(Document, document_id) is None

        # The successful deletion event should remain in the audit log.
        deletion_log = db.scalar(
            select(AuditLog).where(
                AuditLog.actor_id == owner_id,
                AuditLog.action == "document_delete",
                AuditLog.outcome == "success",
                AuditLog.document_id == document_id,
            )
        )

        assert deletion_log is not None, (
            "Successful document deletion must remain in the audit log "
            "even after the document is deleted."
        )



# ---------------------------------------------------------
# Document search and filter tests
# These require GET /documents to implement the query params.
# ---------------------------------------------------------

def test_document_search_filters_visible_documents(test_accounts):
    token = test_accounts["owner_token"]
    unique = uuid4().hex

    finance = create_document(
        token,
        f"Quarterly Finance {unique}",
        f"finance-{unique}.pdf",
        category="Finance",
    )
    engineering = create_document(
        token,
        f"Engineering Notes {unique}",
        f"engineering-{unique}.pdf",
        category="Engineering",
    )

    response = client.get(
        f"/documents?search={unique}",
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert finance["id"] in ids
    assert engineering["id"] in ids

    response = client.get(
        f"/documents?search=finance-{unique}",
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert finance["id"] in ids
    assert engineering["id"] not in ids

    response = client.get(
        "/documents",
        params={"category": "Engineering"},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert engineering["id"] in ids
    assert finance["id"] not in ids

    response = client.get(
        "/documents",
        params={"owner_id": test_accounts["owner_id"]},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert finance["id"] in ids
    assert engineering["id"] in ids


def test_document_search_does_not_expose_unshared_documents(
    test_accounts,
):
    owner_document = create_document(
        test_accounts["owner_token"],
        f"Secret Project {uuid4().hex}",
        "secret-project.pdf",
        category="Confidential",
    )

    response = client.get(
        "/documents",
        params={"search": "Secret Project"},
        headers=auth(test_accounts["viewer_token"]),
    )
    assert response.status_code == 200, response.text
    assert owner_document["id"] not in {
        item["id"] for item in response.json()
    }

    response = client.get(
        "/documents",
        params={"owner_id": test_accounts["owner_id"]},
        headers=auth(test_accounts["viewer_token"]),
    )
    assert response.status_code == 200, response.text
    assert owner_document["id"] not in {
        item["id"] for item in response.json()
    }


def test_document_search_supports_date_filters(test_accounts):
    token = test_accounts["owner_token"]
    unique = uuid4().hex

    document = create_document(
        token,
        f"Date Filter {unique}",
        f"date-{unique}.pdf",
    )

    today = date.today().isoformat()

    response = client.get(
        "/documents",
        params={"date_from": today, "date_to": today},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    assert document["id"] in {
        item["id"] for item in response.json()
    }

def test_cross_document_access_isolation(test_accounts):
    suffix = uuid4().hex

    # Create a second owner with a separate private document.
    with SessionLocal() as db:
        second_owner = User(
            name="Second Isolation Owner",
            email=f"second-owner-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="owner",
            is_active=True,
        )
        db.add(second_owner)
        db.commit()
        db.refresh(second_owner)
        second_owner_token = create_access_token(second_owner)

    owner_a_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]

    document_a = create_document(
        owner_a_token,
        f"Owner A Private {suffix}",
        "owner-a.pdf",
    )
    document_b = create_document(
        second_owner_token,
        f"Owner B Private {suffix}",
        "owner-b.pdf",
    )

    # Owner A can access their own document.
    response = client.get(
        f"/documents/{document_a['id']}",
        headers=auth(owner_a_token),
    )
    assert response.status_code == 200

    # Owner A cannot access Owner B's private document.
    response = client.get(
        f"/documents/{document_b['id']}",
        headers=auth(owner_a_token),
    )
    assert response.status_code == 404

    # A grant to document A must not expose document B.
    response = client.put(
        f"/documents/{document_a['id']}/permissions/"
        f"{test_accounts['viewer_id']}",
        headers=auth(owner_a_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 200, response.text

    response = client.get(
        f"/documents/{document_a['id']}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200

    response = client.get(
        f"/documents/{document_b['id']}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    # Search results must not leak Owner B's document to Owner A.
    response = client.get(
        "/documents",
        params={"search": f"Owner B Private {suffix}"},
        headers=auth(owner_a_token),
    )
    assert response.status_code == 200, response.text
    assert document_b["id"] not in {
        item["id"] for item in response.json()
    }


def test_document_search_rejects_invalid_date_range(test_accounts):
    today = date.today()
    yesterday = today - timedelta(days=1)
    owner_id = test_accounts["owner_id"]

    response = client.get(
        "/documents",
        params={
            "date_from": today.isoformat(),
            "date_to": yesterday.isoformat(),
        },
        headers=auth(test_accounts["owner_token"]),
    )

    assert response.status_code == 422, response.text

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == owner_id,
                AuditLog.action == "document_list",
                AuditLog.outcome == "failure",
                AuditLog.details.contains("Invalid date range"),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, "Invalid date range was not audited"


def test_denied_delete_of_nonexistent_document_is_audited(test_accounts):
    missing_document_id = 2_000_000_001

    response = client.delete(
        f"/documents/{missing_document_id}",
        headers=auth(test_accounts["owner_token"]),
    )

    assert response.status_code == 404

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == test_accounts["owner_id"],
                AuditLog.action == "document_delete",
                AuditLog.outcome == "denied",
                AuditLog.document_id.is_(None),
                AuditLog.details.contains(str(missing_document_id)),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, "Denied delete was not reliably audited"



def test_grant_to_nonexistent_user_is_audited(test_accounts):
    missing_user_id = 2_000_000_002

    document = create_document(
        test_accounts["owner_token"],
        "Grant Audit Test",
        "grant-audit-test.pdf",
    )
    document_id = document["id"]

    response = client.put(
        f"/documents/{document_id}/permissions/{missing_user_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"permission_type": "read"},
    )

    assert response.status_code == 404

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == test_accounts["owner_id"],
                AuditLog.action == "permission_grant",
                AuditLog.outcome == "failure",
                AuditLog.document_id == document_id,
                AuditLog.details.contains(str(missing_user_id)),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, "Failed grant to nonexistent user was not audited"



def test_grant_to_inactive_user_is_audited(test_accounts):
    document = create_document(
        test_accounts["owner_token"],
        "Inactive User Grant Test",
        "inactive-user-grant-test.pdf",
    )
    document_id = document["id"]

    inactive_user_id = 2_000_000_003

    # Create an inactive target user.
    with SessionLocal() as db:
        inactive_user = User(
            name="Inactive Grant Target",
            email=f"inactive-grant-{uuid4().hex}@example.com",
            password_hash="unused-test-password-hash",
            role="viewer",
            is_active=False,
        )
        db.add(inactive_user)
        db.commit()
        db.refresh(inactive_user)
        inactive_user_id = inactive_user.id

    response = client.put(
        f"/documents/{document_id}/permissions/{inactive_user_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"permission_type": "read"},
    )

    assert response.status_code == 404

    with SessionLocal() as db:
        permission = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == inactive_user_id,
            )
        )

        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == test_accounts["owner_id"],
                AuditLog.action == "permission_grant",
                AuditLog.outcome == "failure",
                AuditLog.document_id == document_id,
                AuditLog.details.contains(str(inactive_user_id)),
            )
            .order_by(AuditLog.id.desc())
        )

    assert permission is None, "Permission was created for an inactive user"
    assert log is not None, "Failed grant to inactive user was not audited"

def test_owner_self_grant_is_audited(test_accounts):
    document = create_document(
        test_accounts["owner_token"],
        "Self Grant Audit Test",
        "self-grant-audit-test.pdf",
    )
    document_id = document["id"]
    owner_id = test_accounts["owner_id"]

    response = client.put(
        f"/documents/{document_id}/permissions/{owner_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"permission_type": "read"},
    )

    assert response.status_code == 400

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == owner_id,
                AuditLog.action == "permission_grant",
                AuditLog.outcome == "failure",
                AuditLog.document_id == document_id,
                AuditLog.details.contains("themselves"),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, "Owner self-grant attempt was not audited"



def test_document_listing_is_recorded_in_audit_log(test_accounts):
    owner_token = test_accounts["owner_token"]
    owner_id = test_accounts["owner_id"]

    # Create a document so the listing has something to return.
    create_document(
        owner_token,
        "Document List Audit Test",
        "document-list-audit-test.pdf",
    )

    response = client.get(
        "/documents",
        headers=auth(owner_token),
    )

    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == owner_id,
                AuditLog.action == "document_list",
                AuditLog.outcome == "success",
                AuditLog.details.contains("Returned"),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, (
        "Successful document listing was not recorded in the audit log"
    )


def test_empty_document_update_is_audited(test_accounts):
    owner_token = test_accounts["owner_token"]
    owner_id = test_accounts["owner_id"]

    document = create_document(
        owner_token,
        "Empty Update Audit Test",
        "empty-update-audit-test.pdf",
    )
    document_id = document["id"]

    response = client.patch(
        f"/documents/{document_id}",
        headers=auth(owner_token),
        json={},
    )

    assert response.status_code == 422, response.text

    with SessionLocal() as db:
        log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == owner_id,
                AuditLog.action == "document_update",
                AuditLog.outcome == "failure",
                AuditLog.document_id == document_id,
                AuditLog.details.contains("Empty update request"),
            )
            .order_by(AuditLog.id.desc())
        )

    assert log is not None, "Empty document update was not audited"


def test_editor_cannot_grant_or_revoke_permissions(test_accounts):
    owner_token = test_accounts["owner_token"]
    editor_token = test_accounts["viewer_token"]
    editor_id = test_accounts["viewer_id"]

    document = create_document(
        owner_token,
        "Editor Permission Management Test",
        "editor-permission-test.pdf",
    )
    document_id = document["id"]

    # Owner grants edit access.
    response = client.put(
        f"/documents/{document_id}/permissions/{editor_id}",
        headers=auth(owner_token),
        json={"permission_type": "edit"},
    )
    assert response.status_code == 200, response.text

    # The editor cannot grant access to another user.
    response = client.put(
        f"/documents/{document_id}/permissions/2000000003",
        headers=auth(editor_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 404

    # The editor cannot revoke another user's access.
    response = client.delete(
        f"/documents/{document_id}/permissions/{editor_id}",
        headers=auth(editor_token),
    )
    assert response.status_code == 404

    # The original edit grant must remain unchanged.
    with SessionLocal() as db:
        permission = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == editor_id,
            )
        )
        assert permission is not None
        assert permission.permission_type == "edit"


def test_admin_without_grant_cannot_access_document_api(test_accounts):
    from app.models import User
    from app.security import create_access_token, hash_password

    suffix = uuid4().hex

    with SessionLocal() as db:
        admin = User(
            name="Document Access Test Admin",
            email=f"document-admin-{suffix}@example.com",
            password_hash=hash_password("TestOnly!Password123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_token = create_access_token(admin)

    document = create_document(
        test_accounts["owner_token"],
        "Admin Isolation Test",
        "admin-isolation-test.pdf",
    )
    document_id = document["id"]

    # Admin must not read metadata without an explicit grant.
    response = client.get(
        f"/documents/{document_id}",
        headers=auth(admin_token),
    )
    assert response.status_code == 404

    # Admin must not download the document without a grant.
    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(admin_token),
    )
    assert response.status_code == 404

    # Verify both denied attempts were audited.
    with SessionLocal() as db:
        denied_logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_id == admin.id,
                    AuditLog.document_id == document_id,
                    AuditLog.outcome == "denied",
                )
            ).all()
        )

    assert len(denied_logs) >= 2


def test_document_listing_shows_shared_documents_only(test_accounts):
    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]
    viewer_id = test_accounts["viewer_id"]
    owner_id = test_accounts["owner_id"]

    shared = create_document(
        owner_token,
        f"Shared Report {uuid4().hex}",
        "shared-report.pdf",
    )
    unshared = create_document(
        owner_token,
        f"Private Report {uuid4().hex}",
        "private-report.pdf",
    )

    # Initially, the viewer cannot see either document.
    response = client.get(
        "/documents",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200
    assert shared["id"] not in {d["id"] for d in response.json()}
    assert unshared["id"] not in {d["id"] for d in response.json()}

    # Grant read access to only one document.
    response = client.put(
        f"/documents/{shared['id']}/permissions/{viewer_id}",
        headers=auth(owner_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 200, response.text

    # The viewer sees the shared document, not the unshared one.
    response = client.get(
        "/documents",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200
    visible_ids = {d["id"] for d in response.json()}
    assert shared["id"] in visible_ids
    assert unshared["id"] not in visible_ids

    # Filtering by owner must not bypass the permission scope.
    response = client.get(
        "/documents",
        params={"owner_id": owner_id},
        headers=auth(viewer_token),
    )
    assert response.status_code == 200
    filtered_ids = {d["id"] for d in response.json()}
    assert shared["id"] in filtered_ids
    assert unshared["id"] not in filtered_ids


def test_permission_grant_is_not_saved_when_audit_fails(
    test_accounts, monkeypatch
):
    import app.routers.documents as documents_router

    document = create_document(
        test_accounts["owner_token"],
        "Grant Audit Failure Test",
        "grant-audit-failure.pdf",
    )
    document_id = document["id"]
    viewer_id = test_accounts["viewer_id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit database failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)
    test_client = TestClient(app, raise_server_exceptions=False)

    response = test_client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"permission_type": "read"},
    )
    assert response.status_code == 500

    with SessionLocal() as db:
        permission = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == viewer_id,
            )
        )
        assert permission is None


def test_permission_revoke_is_not_saved_when_audit_fails(
    test_accounts, monkeypatch
):
    import app.routers.documents as documents_router

    document = create_document(
        test_accounts["owner_token"],
        "Revoke Audit Failure Test",
        "revoke-audit-failure.pdf",
    )
    document_id = document["id"]
    viewer_id = test_accounts["viewer_id"]

    grant_response = client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(test_accounts["owner_token"]),
        json={"permission_type": "read"},
    )
    assert grant_response.status_code == 200, grant_response.text

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit database failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)
    test_client = TestClient(app, raise_server_exceptions=False)

    response = test_client.delete(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(test_accounts["owner_token"]),
    )
    assert response.status_code == 500

    with SessionLocal() as db:
        permission = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == viewer_id,
            )
        )
        assert permission is not None
        assert permission.permission_type == "read"


def test_document_delete_is_not_saved_when_audit_fails(
    test_accounts, monkeypatch
):
    import app.routers.documents as documents_router

    document = create_document(
        test_accounts["owner_token"],
        "Delete Audit Failure Test",
        "delete-audit-failure.pdf",
    )
    document_id = document["id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit database failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)
    test_client = TestClient(app, raise_server_exceptions=False)

    response = test_client.delete(
        f"/documents/{document_id}",
        headers=auth(test_accounts["owner_token"]),
    )
    assert response.status_code == 500

    # Document must still exist because transaction was aborted
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        assert doc is not None


def test_document_download_fails_when_audit_write_fails(
    test_accounts, monkeypatch, tmp_path
):
    import app.file_storage as file_storage
    import app.routers.documents as documents_router

    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    # Upload a document first
    pdf_bytes = b"%PDF-1.4 test document download audit failure"
    upload_res = client.post(
        "/documents/upload",
        headers=auth(test_accounts["owner_token"]),
        files={"file": ("test_dl_fail.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit database failure")

    monkeypatch.setattr(documents_router, "record_audit", fail_audit)
    test_client = TestClient(app, raise_server_exceptions=False)

    response = test_client.get(
        f"/documents/{doc_id}/download",
        headers=auth(test_accounts["owner_token"]),
    )
    assert response.status_code == 500


def test_document_listing_pagination(test_accounts):
    token = test_accounts["owner_token"]

    doc_ids = []
    for i in range(4):
        doc = create_document(
            token,
            f"Pagination Test Doc {i} {uuid4().hex}",
            f"pagination_{i}.pdf",
            category="PaginationCategory",
        )
        doc_ids.append(doc["id"])

    # Test limit=2, offset=0
    res1 = client.get(
        "/documents",
        params={"category": "PaginationCategory", "limit": 2, "offset": 0},
        headers=auth(token),
    )
    assert res1.status_code == 200
    items1 = res1.json()
    assert len(items1) == 2

    # Test limit=2, offset=2
    res2 = client.get(
        "/documents",
        params={"category": "PaginationCategory", "limit": 2, "offset": 2},
        headers=auth(token),
    )
    assert res2.status_code == 200
    items2 = res2.json()
    assert len(items2) == 2

    # Items in page 1 and page 2 must be disjoint
    page1_ids = {d["id"] for d in items1}
    page2_ids = {d["id"] for d in items2}
    assert page1_ids.isdisjoint(page2_ids)

    # Invalid pagination parameters must return 422
    assert client.get("/documents", params={"limit": 0}, headers=auth(token)).status_code == 422
    assert client.get("/documents", params={"limit": 101}, headers=auth(token)).status_code == 422
    assert client.get("/documents", params={"offset": -1}, headers=auth(token)).status_code == 422


def test_viewer_metadata_creation_denial_is_audited(test_accounts):
    viewer_id = test_accounts["viewer_id"]
    viewer_token = test_accounts["viewer_token"]

    response = client.post(
        "/documents",
        headers=auth(viewer_token),
        json={
            "title": "Unauthorized Metadata Creation",
            "original_filename": "unauth.pdf",
            "size_bytes": 0,
        },
    )
    assert response.status_code == 403

    with SessionLocal() as db:
        denied_entry = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == viewer_id,
                AuditLog.action == "document_create",
                AuditLog.outcome == "denied",
            )
            .order_by(AuditLog.id.desc())
        )
    assert denied_entry is not None
    assert "Only owners can create documents" in denied_entry.details


def test_seed_demo_accounts_is_safe_and_idempotent():
    import os
    from seed_demo import seed_demo_accounts, DEMO_USERS
    from app.models import User

    # First ensure demo accounts exist by seeding them with env vars
    for _, email, role in DEMO_USERS:
        os.environ[f"DEMO_PASSWORD_{role.upper()}"] = "DemoSecurePass!123"

    with SessionLocal() as db:
        # Run seed
        created = seed_demo_accounts(db=db)
        # Record initial states
        users_before = {
            u.email: (u.password_hash, u.role, u.is_active)
            for u in db.scalars(select(User).where(User.email.in_([e for _, e, _ in DEMO_USERS]))).all()
        }

        # Second run: must detect all accounts exist and create 0
        rerun_created = seed_demo_accounts(db=db)
        assert rerun_created == 0

        # State must remain unchanged
        users_after = {
            u.email: (u.password_hash, u.role, u.is_active)
            for u in db.scalars(select(User).where(User.email.in_([e for _, e, _ in DEMO_USERS]))).all()
        }
        assert users_before == users_after

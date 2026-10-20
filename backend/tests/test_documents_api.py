
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

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

    # Remove only data associated with these test accounts.
    with SessionLocal() as db:
        account_ids = [owner_id, viewer_id]

        owned_document_ids = list(
            db.scalars(
                select(Document.id).where(
                    Document.owner_id.in_(account_ids)
                )
            ).all()
        )

        # Remove audit records before deleting their related users
        # or documents, preserving foreign-key integrity.
        conditions = [AuditLog.actor_id.in_(account_ids)]
        if owned_document_ids:
            conditions.append(
                AuditLog.document_id.in_(owned_document_ids)
            )

        db.execute(delete(AuditLog).where(or_(*conditions)))

        db.execute(
            delete(DocumentPermission).where(
                or_(
                    DocumentPermission.user_id.in_(account_ids),
                    DocumentPermission.granted_by.in_(account_ids),
                    DocumentPermission.document_id.in_(
                        owned_document_ids or [-1]
                    ),
                )
            )
        )

        db.execute(
            delete(Document).where(
                Document.owner_id.in_(account_ids)
            )
        )
        db.execute(
            delete(User).where(User.id.in_(account_ids))
        )
        db.commit()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_document_endpoints_require_authentication():
    assert client.get("/documents").status_code == 401
    assert client.post(
        "/documents",
        json={
            "title": "Unauthenticated",
            "original_filename": "test.pdf",
            "size_bytes": 0,
        },
    ).status_code == 401


def test_owner_can_create_and_read_document(test_accounts):
    token = test_accounts["owner_token"]

    response = client.post(
        "/documents",
        headers=auth(token),
        json={
            "title": "Integration Test Document",
            "description": "Test metadata",
            "category": "Testing",
            "original_filename": "example.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
        },
    )

    assert response.status_code == 201, response.text
    created = response.json()
    document_id = created["id"]

    assert created["owner_id"] == test_accounts["owner_id"]
    assert "storage_key" not in created

    response = client.get(
        f"/documents/{document_id}",
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == document_id


def test_ungranted_user_cannot_read_edit_or_delete(
    test_accounts,
):
    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]

    response = client.post(
        "/documents",
        headers=auth(owner_token),
        json={
            "title": "Private Integration Test",
            "original_filename": "private.pdf",
            "content_type": "application/pdf",
            "size_bytes": 50,
        },
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    # The viewer must not be able to read the metadata.
    response = client.get(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    # The viewer must not be able to modify the document.
    response = client.patch(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
        json={"title": "Unauthorized change"},
    )
    assert response.status_code == 404

    # Only the owner can delete the document.
    response = client.delete(
        f"/documents/{document_id}",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    # Denied requests must be recorded in PostgreSQL.
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

    # Isolate physical files from the development storage directory.
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    owner_token = test_accounts["owner_token"]
    viewer_token = test_accounts["viewer_token"]
    viewer_id = test_accounts["viewer_id"]

    # A minimal PDF-signature test fixture.
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog >> endobj\n"
        b"%%EOF\n"
    )

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

    # A viewer without a grant cannot download.
    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    # The owner grants read access through the API.
    response = client.put(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
        json={"permission_type": "read"},
    )
    assert response.status_code == 200, response.text

    # The granted viewer can download the file.
    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200
    assert response.content == pdf_content

    # Revocation must block the viewer's next download.
    response = client.delete(
        f"/documents/{document_id}/permissions/{viewer_id}",
        headers=auth(owner_token),
    )
    assert response.status_code == 204

    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert response.status_code == 404

    # Denied downloads should have generated audit entries.
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import AuditLog

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

    # Keep test files isolated from private development storage.
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)

    owner_id = test_accounts["owner_id"]
    owner_token = test_accounts["owner_token"]

    # Send an unsupported file type to trigger upload validation.
    response = client.post(
        "/documents/upload",
        headers=auth(owner_token),
        files={
            "file": (
                "malicious.exe",
                b"not an allowed document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code in (400, 415, 422), response.text

    # The failed upload must have an independently committed audit entry.
    with SessionLocal() as db:
        failure_logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_id == owner_id,
                    AuditLog.action == "document_upload",
                    AuditLog.outcome == "failure",
                )
            ).all()
        )

    assert failure_logs, "Failed upload was not recorded in the audit log"

from uuid import uuid4
from datetime import date, timedelta

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

    with SessionLocal() as db:
        account_ids = [owner_id, viewer_id]

        owned_document_ids = list(
            db.scalars(
                select(Document.id).where(
                    Document.owner_id.in_(account_ids)
                )
            ).all()
        )

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

    response = client.get(
        f"/documents/{document_id}/download",
        headers=auth(viewer_token),
    )
    assert response.status_code == 200
    assert response.content == pdf_content

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


def test_document_search_rejects_invalid_date_range(test_accounts):
    today = date.today()
    yesterday = today - timedelta(days=1)

    response = client.get(
        "/documents",
        params={
            "date_from": today.isoformat(),
            "date_to": yesterday.isoformat(),
        },
        headers=auth(test_accounts["owner_token"]),
    )

    assert response.status_code == 422, response.text

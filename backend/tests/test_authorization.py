
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.authorization import get_authorized_document


class FakeDB:
    """Small test double; does not modify PostgreSQL."""

    def __init__(self, document, permission=None):
        self.document = document
        self.permission = permission

    def get(self, model, document_id):
        if (
            self.document is not None
            and self.document.id == document_id
        ):
            return self.document
        return None

    def scalar(self, statement):
        return self.permission


def make_user(user_id, role="viewer"):
    return SimpleNamespace(id=user_id, role=role)


def make_document(owner_id=1, document_id=10):
    return SimpleNamespace(
        id=document_id,
        owner_id=owner_id,
        title="Private test document",
    )


def make_permission(user_id, permission_type):
    return SimpleNamespace(
        user_id=user_id,
        permission_type=permission_type,
    )


def test_owner_can_read_and_edit_own_document():
    owner = make_user(1, "owner")
    document = make_document(owner_id=1)
    db = FakeDB(document)

    assert get_authorized_document(
        db, owner, 10, "read"
    ) is document

    assert get_authorized_document(
        db, owner, 10, "edit"
    ) is document


def test_user_without_grant_cannot_access_document():
    viewer = make_user(2)
    document = make_document(owner_id=1)
    db = FakeDB(document, permission=None)

    with pytest.raises(HTTPException) as exc:
        get_authorized_document(db, viewer, 10, "read")

    assert exc.value.status_code == 404


def test_read_grant_allows_read_but_denies_edit():
    viewer = make_user(2)
    document = make_document(owner_id=1)
    permission = make_permission(2, "read")
    db = FakeDB(document, permission)

    assert get_authorized_document(
        db, viewer, 10, "read"
    ) is document

    with pytest.raises(HTTPException) as exc:
        get_authorized_document(db, viewer, 10, "edit")

    assert exc.value.status_code == 404


def test_edit_grant_allows_read_and_edit():
    viewer = make_user(2)
    document = make_document(owner_id=1)
    permission = make_permission(2, "edit")
    db = FakeDB(document, permission)

    assert get_authorized_document(
        db, viewer, 10, "read"
    ) is document

    assert get_authorized_document(
        db, viewer, 10, "edit"
    ) is document


def test_admin_without_grant_cannot_access_document():
    admin = make_user(3, "admin")
    document = make_document(owner_id=1)
    db = FakeDB(document, permission=None)

    with pytest.raises(HTTPException) as exc:
        get_authorized_document(db, admin, 10, "read")

    assert exc.value.status_code == 404


def test_revoked_permission_blocks_next_access():
    viewer = make_user(2)
    document = make_document(owner_id=1)
    permission = make_permission(2, "read")
    db = FakeDB(document, permission)

    # Access works while the grant exists.
    assert get_authorized_document(
        db, viewer, 10, "read"
    ) is document

    # Simulate revocation in the database.
    db.permission = None

    # The next authorization check must deny access.
    with pytest.raises(HTTPException) as exc:
        get_authorized_document(db, viewer, 10, "read")

    assert exc.value.status_code == 404


def test_missing_document_returns_404():
    viewer = make_user(2)
    db = FakeDB(document=None)

    with pytest.raises(HTTPException) as exc:
        get_authorized_document(db, viewer, 999, "read")

    assert exc.value.status_code == 404

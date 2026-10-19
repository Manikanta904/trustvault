
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentPermission, User


def get_authorized_document(
    db: Session,
    user: User,
    document_id: int,
    required_permission: str = "read",
) -> Document:
    """
    Return a document only when the current user is
    authorized to perform the requested operation.

    Permission rules:
    - The document owner can read and edit their document.
    - A user with read permission can read the document.
    - A user with edit permission can read and edit it.
    - Admin role alone does not grant document-content access.
    """

    if required_permission not in {"read", "edit"}:
        raise ValueError(
            "required_permission must be 'read' or 'edit'"
        )

    document = db.get(Document, document_id)

    # Return 404 for missing and inaccessible documents to
    # avoid revealing whether another user's document exists.
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Owners control their own documents.
    if document.owner_id == user.id:
        return document

    # Look up the current grant in the database on every
    # request. Do not rely on permissions stored in a JWT.
    permission = db.scalar(
        select(DocumentPermission).where(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user.id,
        )
    )

    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    allowed = (
        permission.permission_type == "edit"
        or (
            required_permission == "read"
            and permission.permission_type == "read"
        )
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document

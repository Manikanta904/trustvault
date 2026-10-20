
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.authorization import get_authorized_document
from app.database import SessionLocal, get_db
from app.models import Document, DocumentPermission, User
from app.schemas import DocumentCreate, DocumentResponse, DocumentUpdate
from app.security import get_current_user
from app.security import get_current_user, require_roles
from app.schemas import PermissionGrantRequest, PermissionResponse
from fastapi import File, UploadFile
from fastapi.responses import FileResponse

from app.file_storage import get_storage_path, save_upload


router = APIRouter(prefix="/documents", tags=["Documents"])


def record_upload_failure(user: User, details: str) -> None:
    """Persist an upload failure independently of the upload transaction."""
    try:
        with SessionLocal() as audit_db:
            record_audit(
                db=audit_db,
                actor=user,
                action="document_upload",
                outcome="failure",
                details=details,
            )
            audit_db.commit()
    except Exception:
        # Do not expose internal database errors to the client.
        # Production deployments should alert on audit-write failures.
        # This fallback does not guarantee the event was recorded.
        pass


def get_document_or_audit_denial(
    db: Session,
    user: User,
    document_id: int,
    permission: str,
) -> Document:
    try:
        return get_authorized_document(
            db, user, document_id, permission
        )
    except HTTPException as exc:
        record_audit(
            db=db,
            actor=user,
            action=f"document_{permission}",
            outcome="denied",
            document_id=document_id,
            details=f"HTTP {exc.status_code}",
        )
        db.commit()
        raise


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner")),
):
    document = Document(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        original_filename=payload.original_filename,
        storage_key=uuid4().hex,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        owner_id=user.id,
    )

    db.add(document)
    db.flush()

    record_audit(
        db,
        user,
        action="document_create",
        outcome="success",
        document_id=document.id,
        details="Document metadata created; file upload not yet implemented",
    )

    db.commit()
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    statement = (
        select(Document)
        .outerjoin(
            DocumentPermission,
            DocumentPermission.document_id == Document.id,
        )
        .where(
            or_(
                Document.owner_id == user.id,
                DocumentPermission.user_id == user.id,
            )
        )
        .distinct()
        .order_by(Document.created_at.desc())
    )

    return list(db.scalars(statement).all())


@router.get("/{document_id}", response_model=DocumentResponse)
def read_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = get_document_or_audit_denial(
        db, user, document_id, "read"
    )

    record_audit(
        db, user,
        action="document_read_metadata",
        outcome="success",
        document_id=document.id,
    )
    db.commit()

    return document


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = get_document_or_audit_denial(
        db, user, document_id, "edit"
    )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update",
        )

    for field, value in changes.items():
        setattr(document, field, value)

    record_audit(
        db, user,
        action="document_update",
        outcome="success",
        document_id=document.id,
    )

    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    # Deletion is owner-only, even if another user has edit access.
    if document is None or document.owner_id != user.id:
        record_audit(
            db, user,
            action="document_delete",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    record_audit(
        db, user,
        action="document_delete",
        outcome="success",
        document_id=document.id,
    )

    file_path = None

    try:
        file_path = get_storage_path(document.storage_key)
    except HTTPException:
        # The metadata may exist even if the file is missing.
        pass

    db.delete(document)
    db.commit()

    # Remove the private file after the database transaction succeeds.
    if file_path is not None:
        file_path.unlink(missing_ok=True)

    return None



@router.put(
    "/{document_id}/permissions/{user_id}",
    response_model=PermissionResponse,
)
def grant_document_permission(
    document_id: int,
    user_id: int,
    payload: PermissionGrantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_audit(
            db,
            user,
            action="permission_grant",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(
            status_code=404,
            detail="Target user not found",
        )

    if target.id == user.id:
        raise HTTPException(
            status_code=400,
            detail="You already own this document",
        )

    permission = db.scalar(
        select(DocumentPermission).where(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user_id,
        )
    )

    if permission is None:
        permission = DocumentPermission(
            document_id=document_id,
            user_id=user_id,
            permission_type=payload.permission_type,
            granted_by=user.id,
        )
        db.add(permission)
    else:
        permission.permission_type = payload.permission_type
        permission.granted_by = user.id

    record_audit(
        db,
        user,
        action="permission_grant",
        outcome="success",
        document_id=document_id,
        details=f"Granted {payload.permission_type} to user {user_id}",
    )

    db.commit()
    db.refresh(permission)

    return {
        "document_id": permission.document_id,
        "user_id": permission.user_id,
        "permission_type": permission.permission_type,
    }


@router.delete(
    "/{document_id}/permissions/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_document_permission(
    document_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_audit(
            db,
            user,
            action="permission_revoke",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    permission = db.scalar(
        select(DocumentPermission).where(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user_id,
        )
    )

    if permission is None:
        record_audit(
            db,
            user,
            action="permission_revoke",
            outcome="failure",
            document_id=document_id,
            details=f"No grant exists for user {user_id}",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Permission grant not found",
        )

    db.delete(permission)

    record_audit(
        db,
        user,
        action="permission_revoke",
        outcome="success",
        document_id=document_id,
        details=f"Revoked access for user {user_id}",
    )

    db.commit()
    return None


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Only owners may create new documents.
    if user.role != "owner":
        record_audit(
            db, user,
            action="document_upload",
            outcome="denied",
            details="Only owners can upload documents",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Only owners can upload documents",
        )

    storage_key = None

    try:
        storage_key, filename, size = await save_upload(file)

        document = Document(
            title=(title or filename)[:200],
            description=description,
            category=category,
            original_filename=filename,
            storage_key=storage_key,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size,
            owner_id=user.id,
        )
        db.add(document)
        db.flush()

        record_audit(
            db, user,
            action="document_upload",
            outcome="success",
            document_id=document.id,
            details=f"Uploaded {size} bytes",
        )

        db.commit()
        db.refresh(document)
        return document

    except Exception as exc:
        db.rollback()

        # Remove any file saved before the database failure.
        if storage_key:
            try:
                get_storage_path(storage_key).unlink(missing_ok=True)
            except HTTPException:
                pass

        # Avoid logging raw exception messages or sensitive file details.
        if isinstance(exc, HTTPException):
            failure_details = f"Upload rejected: HTTP {exc.status_code}"
        else:
            failure_details = "Upload failed during storage or database processing"

        record_upload_failure(user, failure_details)
        raise



@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = get_document_or_audit_denial(
        db, user, document_id, "read"
    )

    try:
        path = get_storage_path(document.storage_key)
    except HTTPException as exc:
        record_audit(
            db, user,
            action="document_download",
            outcome="failure",
            document_id=document_id,
            details="Stored file missing or invalid",
        )
        db.commit()
        raise exc

    record_audit(
        db, user,
        action="document_download",
        outcome="success",
        document_id=document.id,
    )
    db.commit()

    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=document.original_filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )
from datetime import date, datetime, time, timedelta, timezone
import logging
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.authorization import get_authorized_document
from app.database import SessionLocal, get_db
from app.file_storage import get_storage_path, save_upload
from app.models import Document, DocumentPermission, User
from app.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    PermissionGrantRequest,
    PermissionResponse,
)
from app.security import get_current_user, require_roles


router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


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
        # Keep the upload's original failure as the client-visible error, but
        # make audit persistence failures visible to application logs.
        # A production deployment should also alert on this condition.
        logger.error(
            "Failed to persist document-upload failure audit event; "
            "the event may be missing."
        )


def record_document_audit(
    db: Session,
    actor: User | None,
    action: str,
    outcome: str,
    document_id: int | None = None,
    details: str | None = None,
) -> None:
    """
    Record a document-related event without violating the audit FK.

    For a requested ID that does not identify an existing document, store
    document_id=NULL and preserve the attempted ID in details instead.
    """
    safe_document_id = document_id

    if document_id is not None and db.get(Document, document_id) is None:
        safe_document_id = None
        requested_id = f"requested_document_id={document_id}"
        details = f"{details}; {requested_id}" if details else requested_id

    record_audit(
        db=db,
        actor=actor,
        action=action,
        outcome=outcome,
        document_id=safe_document_id,
        details=details,
    )


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
        record_document_audit(
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
    user: User = Depends(get_current_user),
):
    if user.role != "owner":
        record_audit(
            db,
            user,
            action="document_create",
            outcome="denied",
            details="Only owners can create documents",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can create documents",
        )

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
    search: str | None = Query(default=None, max_length=200),
    owner_id: int | None = Query(default=None, gt=0),
    category: str | None = Query(default=None, max_length=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List only documents visible to the caller, with optional filters and pagination."""

    if date_from is not None and date_to is not None and date_from > date_to:
        record_audit(
            db,
            user,
            action="document_list",
            outcome="failure",
            details="Invalid date range: date_from is after date_to",
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be on or before date_to",
        )


    # Apply the access-control scope before any user-supplied filters.
    # Filters must never reveal documents the caller cannot already access.
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
    )

    normalized_search = search.strip() if search else ""
    if normalized_search:
        search_pattern = f"%{normalized_search}%"
        statement = statement.where(
            or_(
                Document.title.ilike(search_pattern),
                Document.original_filename.ilike(search_pattern),
            )
        )

    if owner_id is not None:
        statement = statement.where(Document.owner_id == owner_id)

    normalized_category = category.strip() if category else ""
    if normalized_category:
        statement = statement.where(
            Document.category.ilike(normalized_category)
        )

    if date_from is not None:
        start_datetime = datetime.combine(
            date_from, time.min, tzinfo=timezone.utc
        )
        statement = statement.where(Document.created_at >= start_datetime)

    if date_to is not None:
        # Exclusive next-day boundary includes every time on date_to.
        end_datetime = datetime.combine(
            date_to + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        statement = statement.where(Document.created_at < end_datetime)

    statement = (
        statement
        .distinct()
        .order_by(Document.created_at.desc(), Document.id.desc())
    )

    if limit is not None:
        statement = statement.limit(limit)
    if offset:
        statement = statement.offset(offset)

    documents = list(db.scalars(statement).all())

    record_audit(
        db,
        user,
        action="document_list",
        outcome="success",
        details=(
            f"Returned {len(documents)} accessible documents; "
            f"search_used={bool(normalized_search)}; "
            f"limit={limit}; offset={offset}"
        ),
    )
    db.commit()

    return documents


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
        record_audit(
            db,
            user,
            action="document_update",
            outcome="failure",
            document_id=document.id,
            details="Empty update request; no fields provided",
        )
        db.commit()

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
        record_document_audit(
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
        record_document_audit(
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
        record_audit(
            db,
            user,
            action="permission_grant",
            outcome="failure",
            document_id=document_id,
            details=f"Target user {user_id} not found or inactive",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Target user not found",
        )

    if target.id == user.id:
        record_audit(
            db,
            user,
            action="permission_grant",
            outcome="failure",
            document_id=document_id,
            details="Owner attempted to grant permission to themselves",
        )
        db.commit()
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
        record_document_audit(
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
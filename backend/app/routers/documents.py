from datetime import date, datetime, time, timedelta, timezone
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.audit import record_audit
from app.authorization import get_authorized_document
from app.database import SessionLocal, get_db
from app.file_storage import get_storage_path, save_upload
from app.models import AuditLog, Document, DocumentPermission, User
from app.rate_limiter import document_sensitive_limiter
from app.schemas import (
    BulkPermissionGrantRequest,
    BulkPermissionResponse,
    BulkRevokeResponse,
    BulkSummaryResponse,
    DocumentActivityItem,
    DocumentActivityResponse,
    DocumentCreate,
    DocumentPermissionDetailResponse,
    DocumentResponse,
    DocumentUpdate,
    PermissionGrantRequest,
    PermissionResponse,
)
from app.security import get_current_user, require_roles
from app.watermark import generate_watermarked_pdf


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
    action: str | None = None,
) -> Document:
    try:
        return get_authorized_document(
            db, user, document_id, permission
        )
    except HTTPException as exc:
        record_document_audit(
            db=db,
            actor=user,
            action=action or f"document_{permission}",
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
    return DocumentResponse(
        id=document.id,
        title=document.title,
        description=document.description,
        category=document.category,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        owner_id=document.owner_id,
        owner_name=user.name,
        owner_email=user.email,
        user_permission="owner",
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    search: str | None = Query(default=None, max_length=200),
    owner_id: int | None = Query(default=None, gt=0),
    owner_search: str | None = Query(default=None, max_length=100),
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
    OwnerUser = aliased(User)
    UserPerm = aliased(DocumentPermission)

    statement = (
        select(Document, OwnerUser, UserPerm.permission_type)
        .join(OwnerUser, OwnerUser.id == Document.owner_id)
        .outerjoin(
            UserPerm,
            (UserPerm.document_id == Document.id) & (UserPerm.user_id == user.id),
        )
        .where(
            or_(
                Document.owner_id == user.id,
                UserPerm.id.isnot(None),
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

    normalized_owner_search = owner_search.strip() if owner_search else ""
    if normalized_owner_search:
        owner_pattern = f"%{normalized_owner_search}%"
        statement = statement.where(
            or_(
                OwnerUser.name.ilike(owner_pattern),
                OwnerUser.email.ilike(owner_pattern),
            )
        )

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

    statement = statement.order_by(Document.created_at.desc(), Document.id.desc())

    if limit is not None:
        statement = statement.limit(limit)
    if offset:
        statement = statement.offset(offset)

    rows = db.execute(statement).all()
    documents = [
        DocumentResponse(
            id=doc.id,
            title=doc.title,
            description=doc.description,
            category=doc.category,
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            owner_id=doc.owner_id,
            owner_name=owner.name if owner else None,
            owner_email=owner.email if owner else None,
            user_permission="owner" if doc.owner_id == user.id else (perm_type or "read"),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc, owner, perm_type in rows
    ]

    record_audit(
        db,
        user,
        action="document_list",
        outcome="success",
        details=(
            f"Returned {len(documents)} accessible documents; "
            f"search_used={bool(normalized_search)}; "
            f"owner_search_used={bool(normalized_owner_search)}; "
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

    owner = db.get(User, document.owner_id)
    effective_perm = "owner" if document.owner_id == user.id else db.scalar(
        select(DocumentPermission.permission_type).where(
            DocumentPermission.document_id == document.id,
            DocumentPermission.user_id == user.id,
        )
    )

    record_audit(
        db, user,
        action="document_read_metadata",
        outcome="success",
        document_id=document.id,
    )
    db.commit()

    return DocumentResponse(
        id=document.id,
        title=document.title,
        description=document.description,
        category=document.category,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        owner_id=document.owner_id,
        owner_name=owner.name if owner else None,
        owner_email=owner.email if owner else None,
        user_permission=effective_perm or "read",
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


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

    owner = db.get(User, document.owner_id)
    effective_perm = "owner" if document.owner_id == user.id else "edit"

    return DocumentResponse(
        id=document.id,
        title=document.title,
        description=document.description,
        category=document.category,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        owner_id=document.owner_id,
        owner_name=owner.name if owner else None,
        owner_email=owner.email if owner else None,
        user_permission=effective_perm,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


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


@router.get(
    "/{document_id}/permissions",
    response_model=list[DocumentPermissionDetailResponse],
)
def list_document_permissions(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_document_audit(
            db,
            user,
            action="permission_list",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    statement = (
        select(DocumentPermission, User)
        .join(User, User.id == DocumentPermission.user_id)
        .where(DocumentPermission.document_id == document_id)
        .order_by(DocumentPermission.created_at.desc(), DocumentPermission.id.desc())
    )
    rows = db.execute(statement).all()

    results = [
        DocumentPermissionDetailResponse(
            id=perm.id,
            document_id=perm.document_id,
            user_id=perm.user_id,
            user_name=target_user.name,
            user_email=target_user.email,
            permission_type=perm.permission_type,
            created_at=perm.created_at,
        )
        for perm, target_user in rows
    ]

    record_audit(
        db,
        user,
        action="permission_list",
        outcome="success",
        document_id=document_id,
        details=f"Listed {len(results)} permissions",
    )
    db.commit()

    return results


@router.get(
    "/{document_id}/permissions/bulk-summary",
    response_model=BulkSummaryResponse,
)
def get_bulk_permission_summary(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Calculate summary count of eligible active employees for bulk sharing.
    Owner-only operation. Does not grant access or write grant audit events.
    Eligible roles: Active accounts ('viewer', 'owner', 'admin' if active) excluding the document owner.
    """
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_document_audit(
            db,
            user,
            action="permission_bulk_summary",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Eligible active employees excluding the document owner
    eligible_users = list(
        db.scalars(
            select(User).where(
                User.is_active == True,
                User.id != user.id,
            )
        ).all()
    )
    eligible_count = len(eligible_users)

    existing_grant_count = (
        db.scalar(
            select(func.count(DocumentPermission.id)).where(
                DocumentPermission.document_id == document_id
            )
        )
        or 0
    )
    new_grant_count = max(0, eligible_count - existing_grant_count)

    record_audit(
        db,
        user,
        action="permission_bulk_summary",
        outcome="success",
        document_id=document.id,
        details=(
            f"Calculated bulk summary: {eligible_count} eligible employees "
            f"({new_grant_count} new, {existing_grant_count} existing)"
        ),
    )
    db.commit()

    return {
        "document_id": document.id,
        "eligible_count": eligible_count,
        "new_grant_count": new_grant_count,
        "existing_grant_count": existing_grant_count,
    }


@router.post(
    "/{document_id}/permissions/bulk",
    response_model=BulkPermissionResponse,
)
def bulk_grant_document_permissions(
    document_id: int,
    payload: BulkPermissionGrantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Share a document with all active employees in a single atomic transaction.
    Owner-only operation. Creates/updates individual permission rows for each active
    employee (excluding the owner) with correct granted_by attribution and audit logging.
    """
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_document_audit(
            db,
            user,
            action="permission_bulk_grant",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        eligible_users = list(
            db.scalars(
                select(User).where(
                    User.is_active == True,
                    User.id != user.id,
                ).order_by(User.id.asc())
            ).all()
        )

        existing_perms = {
            p.user_id: p
            for p in db.scalars(
                select(DocumentPermission).where(
                    DocumentPermission.document_id == document_id
                )
            ).all()
        }

        affected_count = 0
        new_grants = 0
        updated_grants = 0

        for target_user in eligible_users:
            if target_user.id in existing_perms:
                perm = existing_perms[target_user.id]
                if perm.permission_type != payload.permission_type:
                    perm.permission_type = payload.permission_type
                    perm.granted_by = user.id
                    updated_grants += 1
                affected_count += 1
            else:
                perm = DocumentPermission(
                    document_id=document.id,
                    user_id=target_user.id,
                    permission_type=payload.permission_type,
                    granted_by=user.id,
                )
                db.add(perm)
                new_grants += 1
                affected_count += 1

        record_audit(
            db=db,
            actor=user,
            action="permission_bulk_grant",
            outcome="success",
            document_id=document.id,
            details=(
                f"Bulk granted '{payload.permission_type}' to {affected_count} active employees "
                f"({new_grants} new, {updated_grants} updated)"
            ),
        )
        db.commit()

        return {
            "document_id": document.id,
            "permission_type": payload.permission_type,
            "affected_count": affected_count,
        }
    except Exception:
        db.rollback()
        record_audit(
            db=db,
            actor=user,
            action="permission_bulk_grant",
            outcome="failure",
            document_id=document_id,
            details="Bulk grant transaction failed and was rolled back",
        )
        db.commit()
        raise


@router.delete(
    "/{document_id}/permissions/bulk",
    response_model=BulkRevokeResponse,
)
def bulk_revoke_document_permissions(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Revoke all shared permissions on a document in a single atomic transaction.
    Owner-only operation. Removes all recipient permission records without
    affecting the document itself or historical audit records.
    """
    document = db.get(Document, document_id)

    if document is None or document.owner_id != user.id:
        record_document_audit(
            db,
            user,
            action="permission_bulk_revoke",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        perms = list(
            db.scalars(
                select(DocumentPermission).where(
                    DocumentPermission.document_id == document_id
                )
            ).all()
        )
        revoked_count = len(perms)
        for p in perms:
            db.delete(p)

        record_audit(
            db=db,
            actor=user,
            action="permission_bulk_revoke",
            outcome="success",
            document_id=document.id,
            details=f"Bulk revoked {revoked_count} permissions",
        )
        db.commit()

        return {
            "document_id": document.id,
            "revoked_count": revoked_count,
        }
    except Exception:
        db.rollback()
        record_audit(
            db=db,
            actor=user,
            action="permission_bulk_revoke",
            outcome="failure",
            document_id=document_id,
            details="Bulk revoke transaction failed and was rolled back",
        )
        db.commit()
        raise


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
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
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

    document_sensitive_limiter.check(f"user_{user.id}_upload")

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
        return DocumentResponse(
            id=document.id,
            title=document.title,
            description=document.description,
            category=document.category,
            original_filename=document.original_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            owner_id=document.owner_id,
            owner_name=user.name,
            owner_email=user.email,
            user_permission="owner",
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

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



@router.get("/{document_id}/view")
def view_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Secure in-browser document viewing.
    Permits the document owner and recipients with valid 'read' or 'edit' access.
    Returns inline content disposition with restrictive security and cache headers.
    """
    document = get_document_or_audit_denial(
        db, user, document_id, "read", action="document_view"
    )

    try:
        path = get_storage_path(document.storage_key)
    except HTTPException as exc:
        record_audit(
            db,
            user,
            action="document_view",
            outcome="failure",
            document_id=document_id,
            details="Stored file missing or invalid",
        )
        db.commit()
        raise exc

    record_audit(
        db,
        user,
        action="document_view",
        outcome="success",
        document_id=document.id,
    )
    db.commit()

    media_type = document.content_type or "application/pdf"

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=document.original_filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store, must-revalidate",
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'",
        },
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Download the document file.
    - Owner: downloads the original stored file.
    - Shared user ('read' or 'edit'): downloads a viewer-specific watermarked copy.
    - Unauthorized or revoked user: denied with 404.
    """
    document = db.get(Document, document_id)

    # Permission check: owner or shared read/edit recipient
    user_perm = None
    if document is not None and document.owner_id != user.id:
        user_perm = db.scalar(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == user.id,
            )
        )

    if document is None or (document.owner_id != user.id and user_perm is None):
        record_document_audit(
            db,
            user,
            action="document_download",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller not authorized to download",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document_sensitive_limiter.check(f"user_{user.id}_download")

    try:
        path = get_storage_path(document.storage_key)
    except HTTPException as exc:
        record_audit(
            db,
            user,
            action="document_download",
            outcome="failure",
            document_id=document_id,
            details="Stored file missing or invalid",
        )
        db.commit()
        raise exc

    # Case 1: Owner downloads original stored file
    if document.owner_id == user.id:
        record_audit(
            db,
            user,
            action="document_download",
            outcome="success",
            document_id=document.id,
            details="Owner downloaded original file",
        )
        db.commit()

        return FileResponse(
            path=path,
            media_type="application/octet-stream",
            filename=document.original_filename,
            content_disposition_type="attachment",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store, must-revalidate",
            },
        )

    # Case 2: Shared viewer ('read' or 'edit') downloads watermarked PDF
    is_pdf = (
        document.content_type == "application/pdf"
        or document.original_filename.lower().endswith(".pdf")
    )
    if not is_pdf:
        record_audit(
            db,
            user,
            action="document_download",
            outcome="failure",
            document_id=document.id,
            details="Shared downloads require PDF watermarking, but document is non-PDF",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF documents support secure watermarked downloads for shared recipients.",
        )

    watermarked_bytes = generate_watermarked_pdf(
        source_path=path,
        viewer=user,
        document=document,
        is_download=True,
    )

    record_audit(
        db,
        user,
        action="document_download",
        outcome="success",
        document_id=document.id,
        details=f"Shared user {user.email} downloaded watermarked copy",
    )
    db.commit()

    download_filename = f"watermarked_{document.original_filename}"
    return Response(
        content=watermarked_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store, must-revalidate",
        },
    )


@router.get(
    "/{document_id}/activity",
    response_model=DocumentActivityResponse,
)
def get_document_activity(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Retrieve activity and download history for a document. Restricted to document owner.
    """
    document = db.get(Document, document_id)
    if document is None or document.owner_id != user.id:
        record_document_audit(
            db,
            user,
            action="document_activity",
            outcome="denied",
            document_id=document_id,
            details="Missing document or caller is not owner",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    statement = (
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(AuditLog.document_id == document_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(100)
    )
    rows = db.execute(statement).all()

    items = [
        DocumentActivityItem(
            id=log.id,
            actor_id=log.actor_id,
            actor_name=actor.name if actor else None,
            actor_email=actor.email if actor else None,
            action=log.action,
            outcome=log.outcome,
            details=log.details,
            created_at=log.created_at,
        )
        for log, actor in rows
    ]

    record_audit(
        db,
        user,
        action="document_activity",
        outcome="success",
        document_id=document.id,
        details=f"Retrieved {len(items)} activity entries",
    )
    db.commit()

    return DocumentActivityResponse(
        document_id=document.id,
        items=items,
    )
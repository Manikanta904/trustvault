
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session



from app.audit import record_audit
from app.database import get_db
from app.models import AuditLog, User
from app.security import get_current_user


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/audit-logs")
def list_audit_logs(
    action: str | None = Query(default=None, max_length=50),
    outcome: str | None = Query(default=None),
    actor_id: int | None = Query(default=None, ge=1),
    document_id: int | None = Query(default=None, ge=1),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        record_audit(
            db=db,
            actor=user,
            action="admin_audit_logs_read",
            outcome="denied",
            details="Non-admin attempted to access audit logs",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )

    if start_date and end_date and start_date > end_date:

        raise HTTPException(
            status_code=422,
            detail="start_date must be before or equal to end_date",
        )

    statement = select(AuditLog)

    if action:
        statement = statement.where(AuditLog.action == action)

    if outcome:
        if outcome not in {"success", "denied", "failure"}:

            raise HTTPException(
                status_code=422,
                detail="Invalid outcome",
            )
        statement = statement.where(AuditLog.outcome == outcome)

    if actor_id is not None:
        statement = statement.where(AuditLog.actor_id == actor_id)

    if document_id is not None:
        statement = statement.where(AuditLog.document_id == document_id)

    if start_date:
        statement = statement.where(
            AuditLog.created_at >= start_date
        )

    if end_date:
        statement = statement.where(
            AuditLog.created_at <= end_date
        )

    statement = (
        statement
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )

    entries = db.scalars(statement).all()

    # Explicit response fields prevent unrelated model fields
    # from being exposed if the model changes in the future.
    return {
        "items": [
            {
                "id": entry.id,
                "actor_id": entry.actor_id,
                "document_id": entry.document_id,
                "action": entry.action,
                "outcome": entry.outcome,
                "details": entry.details,
                "created_at": entry.created_at,
            }
            for entry in entries
        ],
        "limit": limit,
        "offset": offset,
    }

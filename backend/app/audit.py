from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    outcome: str,
    document_id: int | None = None,
    details: str | None = None,
) -> None:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        document_id=document_id,
        action=action,
        outcome=outcome,
        details=details,
    )
    db.add(entry)
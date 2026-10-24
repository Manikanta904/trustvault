from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.models import User
from app.schemas import UserSearchResult
from app.security import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/search", response_model=list[UserSearchResult])
def search_users(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search term matching employee name or email",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of users to return",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Search active employees by name or email for document sharing.
    - Requires authenticated session.
    - Permitted for document owners and administrators.
    - Excludes inactive accounts.
    - Excludes the calling user (cannot grant access to self).
    - Returns minimal fields (id, name, email, role). Never exposes password hashes or tokens.
    """
    if user.role not in {"owner", "admin"}:
        record_audit(
            db=db,
            actor=user,
            action="user_search",
            outcome="denied",
            details="User with role 'viewer' attempted to search users",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to search users",
        )

    clean_query = q.strip()
    if not clean_query:
        return []

    pattern = f"%{clean_query}%"
    statement = (
        select(User)
        .where(
            User.is_active == True,
            User.id != user.id,
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
            ),
        )
        .order_by(User.name.asc(), User.id.asc())
        .limit(limit)
    )

    matching_users = list(db.scalars(statement).all())

    record_audit(
        db=db,
        actor=user,
        action="user_search",
        outcome="success",
        details=f"query='{clean_query[:30]}'; returned {len(matching_users)} users",
    )
    db.commit()

    return matching_users

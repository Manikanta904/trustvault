
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import User
from app.security import (
    create_access_token,
    get_current_user,
    verify_password,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local prototype only. We will use Alembic
    # migrations for the production database.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="TrustVault API",
    description="Secure document sharing and auditing",
    version="0.1.0",
    lifespan=lifespan,
)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form.username.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(
            form.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@app.get("/auth/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
):
    return user

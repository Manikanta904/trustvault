
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.routers.documents import router as documents_router
from app.database import Base, engine, get_db
from app.models import User
from app.security import (
    create_access_token,
    get_current_user,
    verify_password,
)
from sqlalchemy.exc import IntegrityError
from app.schemas import UserRegister
from app.security import hash_password
from app.audit import record_audit
from app.rate_limiter import (
    get_client_ip,
    login_rate_limiter,
    register_rate_limiter,
)

from app.routers.admin import router as admin_router
from app.routers.users import router as users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local prototype only. We will use Alembic
    # migrations for the production database.

    yield


app = FastAPI(
    title="TrustVault API",
    description="Secure document sharing and auditing",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for frontend-backend communication
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://trustvault-secure-ahte.onrender.com",
]

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    for origin in cors_origins_env.split(","):
        cleaned = origin.strip()
        if cleaned and cleaned not in default_origins:
            default_origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(users_router)
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

@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        register_rate_limiter.check(client_ip)
    except HTTPException as exc:
        record_audit(
            db=db,
            actor=None,
            action="rate_limit_exceeded",
            outcome="denied",
            details=f"Registration rate limit exceeded from {client_ip}",
        )
        db.commit()
        raise exc

    email = str(payload.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role="owner",
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    return user

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    try:
        login_rate_limiter.check(client_ip)
    except HTTPException as exc:
        record_audit(
            db=db,
            actor=None,
            action="rate_limit_exceeded",
            outcome="denied",
            details=f"Login rate limit exceeded from {client_ip}",
        )
        db.commit()
        raise exc

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
        record_audit(
            db=db,
            actor=user,
            action="login",
            outcome="denied",
            details="Invalid credentials or inactive account",
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    record_audit(
        db=db,
        actor=user,
        action="login",
        outcome="success",
        details="User authenticated successfully",
    )
    db.commit()

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@app.get("/auth/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
):
    return user

import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9\s]", value):
            raise ValueError("Password must contain at least one special character")
        return value



class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(
        default="application/octet-stream",
        max_length=150,
    )
    size_bytes: int = Field(default=0, ge=0)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)


class DocumentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    category: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    owner_id: int
    owner_name: str | None = None
    owner_email: str | None = None
    user_permission: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentActivityItem(BaseModel):
    id: int
    actor_id: int | None
    actor_name: str | None = None
    actor_email: str | None = None
    action: str
    outcome: str
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentActivityResponse(BaseModel):
    document_id: int
    items: list[DocumentActivityItem]

class PermissionGrantRequest(BaseModel):
    permission_type: str = Field(
        pattern="^(read|edit)$"
    )


class PermissionResponse(BaseModel):
    document_id: int
    user_id: int
    permission_type: str


class UserSearchResult(BaseModel):
    id: int
    name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class DocumentPermissionDetailResponse(BaseModel):
    id: int
    document_id: int
    user_id: int
    user_name: str
    user_email: str
    permission_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkPermissionGrantRequest(BaseModel):
    permission_type: str = Field(
        pattern="^(read|edit)$",
        description="Permission level to grant to all active employees: 'read' or 'edit'",
    )


class BulkPermissionResponse(BaseModel):
    document_id: int
    permission_type: str
    affected_count: int


class BulkSummaryResponse(BaseModel):
    document_id: int
    eligible_count: int
    new_grant_count: int
    existing_grant_count: int


class BulkRevokeResponse(BaseModel):
    document_id: int
    revoked_count: int
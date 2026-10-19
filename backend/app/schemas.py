from pydantic import BaseModel, ConfigDict, Field


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


from datetime import datetime

# Keep the other imports and schemas.

class DocumentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    category: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PermissionGrantRequest(BaseModel):
    permission_type: str = Field(
        pattern="^(read|edit)$"
    )


class PermissionResponse(BaseModel):
    document_id: int
    user_id: int
    permission_type: str
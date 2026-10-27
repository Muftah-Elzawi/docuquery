from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DocumentStatus, Role


class RegisterRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: Role
    workspace_id: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.member


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    uploaded_by: str | None
    filename: str
    pages: int
    status: DocumentStatus
    error: str | None
    extracted_fields: dict | None
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[str] | None = None


class SourceOut(BaseModel):
    number: int
    document_id: str
    filename: str
    page: int
    similarity: float
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class WorkspaceStats(BaseModel):
    users: int
    documents: int
    chunks: int
    failed_documents: int

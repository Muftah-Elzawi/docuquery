from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.models import Chunk, Document, DocumentStatus, User
from app.schemas import CreateUserRequest, UserOut, WorkspaceStats
from app.security import AdminUser, DbSession, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(admin: AdminUser, db: DbSession):
    return db.scalars(select(User).where(User.workspace_id == admin.workspace_id).order_by(User.created_at)).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: CreateUserRequest, admin: AdminUser, db: DbSession):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=body.role,
        workspace_id=admin.workspace_id,  # admins can only add users to their own workspace
    )
    db.add(user)
    db.commit()
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, admin: AdminUser, db: DbSession):
    user = db.get(User, user_id)
    if user is None or user.workspace_id != admin.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't delete yourself")
    db.delete(user)
    db.commit()


@router.get("/stats", response_model=WorkspaceStats)
def stats(admin: AdminUser, db: DbSession):
    ws = admin.workspace_id
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    return WorkspaceStats(
        users=count(select(func.count()).select_from(User).where(User.workspace_id == ws)),
        documents=count(select(func.count()).select_from(Document).where(Document.workspace_id == ws)),
        chunks=count(select(func.count()).select_from(Chunk).where(Chunk.workspace_id == ws)),
        failed_documents=count(
            select(func.count())
            .select_from(Document)
            .where(Document.workspace_id == ws, Document.status == DocumentStatus.failed)
        ),
    )

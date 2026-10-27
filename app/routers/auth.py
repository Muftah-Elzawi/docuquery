from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.models import Role, User, Workspace
from app.schemas import RegisterRequest, TokenResponse, UserOut
from app.security import CurrentUser, DbSession, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession):
    """Create a new workspace. The person who creates it becomes its admin."""
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    workspace = Workspace(name=body.workspace_name)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=Role.admin, workspace=workspace)
    db.add_all([workspace, user])
    db.commit()
    return TokenResponse(access_token=create_access_token(user))


@router.post("/login", response_model=TokenResponse)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    # Same error for unknown email and wrong password, so emails can't be probed.
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user

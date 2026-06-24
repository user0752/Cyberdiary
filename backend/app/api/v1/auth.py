"""Auth API endpoints - register, login, current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.memo import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[TokenResponse])
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user and return a JWT token."""
    try:
        user = await auth_service.register_user(db, data.username, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    token = auth_service.issue_token(user)
    return ApiResponse(data=TokenResponse(
        access_token=token,
        username=user.username,
    ))


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return a JWT token."""
    user = await auth_service.authenticate_user(db, data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = auth_service.issue_token(user)
    return ApiResponse(data=TokenResponse(
        access_token=token,
        username=user.username,
    ))


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(current_user: User | None = Depends(get_current_user)):
    """Return the current authenticated user, or 401 if not logged in."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return ApiResponse(data=UserResponse.model_validate(current_user))

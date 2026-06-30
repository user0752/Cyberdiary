"""Auth API endpoints - register, login, current user."""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_current_user, get_db
from app.core.security import decode_access_token, revoke_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.memo import ApiResponse
from app.services import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# P2-14: per-IP login attempt limiter (in-memory, single-process).
# Nginx already rate-limits at the edge (auth_limit zone, 10 r/s), but that
# only blunts brute force at high QPS — it does not stop a slow drip of
# password guesses. This counter locks out an IP for WINDOW seconds after
# MAX_FAILURES bad attempts. Multi-process deployments should move this to
# Redis, but for the 4c/4G single-worker target the in-memory counter is
# sufficient and avoids adding a Redis round-trip on every login.
_LOGIN_MAX_FAILURES = 5
_LOGIN_WINDOW_SECONDS = 300  # 5 min lockout after 5 failures
_login_failures: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For from the nginx reverse proxy; fall back to the
    # direct peer so the limiter still works in dev without a proxy.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_locked(ip: str) -> bool:
    now = time.monotonic()
    attempts = [t for t in _login_failures[ip] if now - t < _LOGIN_WINDOW_SECONDS]
    _login_failures[ip] = attempts
    return len(attempts) >= _LOGIN_MAX_FAILURES


def _record_failure(ip: str) -> None:
    _login_failures[ip].append(time.monotonic())


def _clear_failures(ip: str) -> None:
    _login_failures.pop(ip, None)


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
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return a JWT token."""
    ip = _client_ip(request)
    if _is_locked(ip):
        logger.warning("Login blocked for IP %s (too many failures)", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )
    user = await auth_service.authenticate_user(db, data.username, data.password)
    if user is None:
        _record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    _clear_failures(ip)
    token = auth_service.issue_token(user)
    return ApiResponse(data=TokenResponse(
        access_token=token,
        username=user.username,
    ))


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Revoke the current access token (jti blacklist).

    The client should also discard the token locally. Subsequent requests
    using the same token will be rejected by the auth dependency.
    """
    if credentials is None:
        # Already logged out — return success idempotently.
        return ApiResponse(data=None)
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return ApiResponse(data=None)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        await revoke_token(jti, float(exp))
    return ApiResponse(data=None)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(current_user: User | None = Depends(get_current_user)):
    """Return the current authenticated user, or 401 if not logged in."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return ApiResponse(data=UserResponse.model_validate(current_user))

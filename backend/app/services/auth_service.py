"""Auth service - user registration, password hashing, token issuance."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    """Create a new user. Raises ValueError if username is taken."""
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Username already taken")

    user = User(
        username=username,
        hashed_password=_hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """Verify credentials and return the user, or None if invalid."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not _verify_password(password, user.hashed_password):
        return None
    return user


def issue_token(user: User) -> str:
    """Issue a JWT access token for the given user."""
    return create_access_token({"sub": user.id, "username": user.username})

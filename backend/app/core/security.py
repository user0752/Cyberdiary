"""JWT authentication and AES-256-GCM encryption utilities."""

import base64
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- JWT ---

ALGORITHM = "HS256"

# In-process fallback for revoked-token tracking when Redis is not configured.
# Each entry maps jti -> expiry epoch; entries are purged once they expire.
_revoked_local: dict[str, float] = {}


async def create_access_token_async(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT. Adds a ``jti`` claim so the token can be
    individually revoked via :func:`revoke_token` (e.g. on logout).

    Async because jti revocation state is backed by Redis when available.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Sync wrapper retained for backward compatibility with existing
    callers that don't need revocation. New code should prefer the async
    version so a jti is always emitted.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


async def revoke_token(jti: str, exp_epoch: float) -> None:
    """Mark a token's jti as revoked until its natural expiry.

    Uses Redis when available (so revocation works across multiple workers),
    otherwise falls back to an in-process dict (single-worker mode only).
    """
    # Local fallback
    _revoked_local[jti] = exp_epoch
    # Redis (multi-worker safe)
    try:
        from app.core.redis import get_redis
        r = get_redis()
        if r is not None:
            ttl = max(1, int(exp_epoch - datetime.now(timezone.utc).timestamp()))
            await r.setex(f"jwt:revoked:{jti}", ttl, "1")
    except Exception:
        logger.warning("Redis revocation write failed; in-process fallback active", exc_info=True)


async def is_token_revoked(jti: str) -> bool:
    """Check whether a jti has been revoked. Cleans expired local entries."""
    now = datetime.now(timezone.utc).timestamp()
    # Purge expired local entries to bound memory
    expired = [k for k, v in _revoked_local.items() if v <= now]
    for k in expired:
        _revoked_local.pop(k, None)
    if jti in _revoked_local:
        return True
    try:
        from app.core.redis import get_redis
        r = get_redis()
        if r is not None:
            return bool(await r.exists(f"jwt:revoked:{jti}"))
    except Exception:
        pass
    return False


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


# --- AES-256-GCM for API Key encryption ---

PBKDF2_ITERATIONS = 600_000
SALT_LENGTH = 16
KEY_LENGTH = 32


def _encryption_source() -> str:
    """Return the key material used for AES key derivation.

    Uses ENCRYPTION_KEY if set; falls back to SECRET_KEY for backward
    compatibility with existing encrypted API keys.
    """
    return settings.encryption_key or settings.secret_key


def _derive_aes_key_maybe_previous(salt: bytes) -> bytes:
    """Derive AES key from current encryption source. Raises if salt came from previous key."""
    raw = _encryption_source().encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", raw, salt, PBKDF2_ITERATIONS, dklen=KEY_LENGTH)


def _derive_aes_key_previous(salt: bytes) -> bytes:
    """Derive AES key from PREVIOUS_SECRET_KEY for backward compatibility."""
    raw = settings.previous_secret_key.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", raw, salt, PBKDF2_ITERATIONS, dklen=KEY_LENGTH)


def _get_old_format_key(key_bytes: bytes) -> bytes:
    """Derive 32-byte key from raw bytes using zero-padding (old format)."""
    if len(key_bytes) >= 32:
        return key_bytes[:32]
    return key_bytes.ljust(32, b"\x00")


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key string. Returns base64(salt + nonce + ciphertext)."""
    salt = os.urandom(SALT_LENGTH)
    key = _derive_aes_key_maybe_previous(salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(salt + nonce + ciphertext).decode("utf-8")


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt an encrypted API key string.

    Tries in order: new format (current key) → new format (previous key) →
    old format (current key) → old format (previous key).

    This supports seamless SECRET_KEY rotation.
    """
    raw = base64.b64decode(encrypted)
    current_key_bytes = _encryption_source().encode("utf-8")
    previous_key_bytes = settings.previous_secret_key.encode("utf-8") if settings.previous_secret_key else None

    # Strategy 1: New format (salt + nonce + ciphertext) with PBKDF2-derived key
    if len(raw) >= SALT_LENGTH + 12:
        salt = raw[:SALT_LENGTH]
        nonce = raw[SALT_LENGTH:SALT_LENGTH + 12]
        ciphertext = raw[SALT_LENGTH + 12:]
        # Try current key
        try:
            key = _derive_aes_key_maybe_previous(salt)
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception:
            pass
        # Try previous key
        if previous_key_bytes:
            try:
                key = _derive_aes_key_previous(salt)
                aesgcm = AESGCM(key)
                return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
            except Exception:
                pass

    # Strategy 2: Old format (nonce + ciphertext) with zero-padded key
    nonce = raw[:12]
    ciphertext = raw[12:]
    # Try current key
    try:
        aesgcm = AESGCM(_get_old_format_key(current_key_bytes))
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception:
        pass
    # Try previous key
    if previous_key_bytes:
        aesgcm = AESGCM(_get_old_format_key(previous_key_bytes))
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    # If we get here, nothing worked
    raise ValueError("Failed to decrypt API key — try re-saving the model configuration")

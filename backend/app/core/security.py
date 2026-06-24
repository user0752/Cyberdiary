"""JWT authentication and AES-256-GCM encryption utilities."""

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from app.core.config import settings

# --- JWT ---

ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


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

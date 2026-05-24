"""JWT authentication and AES-256-GCM encryption utilities."""

import base64
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

# Derive a 256-bit key from SECRET_KEY via SHA-256 padding
def _get_aes_key() -> bytes:
    raw = settings.secret_key.encode("utf-8")
    if len(raw) >= 32:
        return raw[:32]
    # Pad to 32 bytes with zeros (simple derivation; production should use PBKDF2)
    return raw.ljust(32, b"\x00")


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key string. Returns base64(nonce + ciphertext)."""
    key = _get_aes_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt a previously encrypted API key string."""
    key = _get_aes_key()
    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")

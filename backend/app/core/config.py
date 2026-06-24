from pydantic import field_validator
from pydantic_settings import BaseSettings


# Known weak defaults that must be rejected
_WEAK_SECRET_KEYS = frozenset({
    "change-me-to-a-random-string",
    "dev-secret-key-change-in-production",
})


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/cybernote.db"

    # JWT
    secret_key: str = ""
    access_token_expire_minutes: int = 1440
    # Optional: previous SECRET_KEY for key rotation. Set this when you change
    # SECRET_KEY so existing encrypted API keys can still be decrypted.
    # Remove it after all models have been re-saved with the new key.
    previous_secret_key: str = ""

    @field_validator("secret_key", mode="before")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "SECRET_KEY is not set. Generate a strong key:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if v in _WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY must not use the default value. "
                "Generate a random key with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters (got {len(v)}). "
                "Generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    # Auth — default to JWT for security. Set AUTH_MODE=none explicitly for
    # local single-user dev if you do not need authentication. AUTH_MODE=none
    # will trigger a loud startup warning to prevent accidental public exposure.
    auth_mode: str = "jwt"  # "none" | "jwt"

    # Encryption key for API keys (AES-256-GCM). If empty, falls back to
    # secret_key for backward compatibility. Set a separate ENCRYPTION_KEY
    # so that a leaked SECRET_KEY (JWT) cannot decrypt stored API keys.
    encryption_key: str = ""

    # Redis (optional — enables multi-instance deployment)
    # If empty, in-memory state is used (single-process only)
    redis_url: str = ""

    # CORS — default restricted to the local Vite dev server. For production
    # set ALLOWED_ORIGINS to a comma-separated list of trusted origins.
    # NOTE: allow_credentials=True is enabled in main.py, so a wildcard "*"
    # is both insecure and rejected by browsers; never default to "*".
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # App
    app_name: str = "CyberNote"
    app_version: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

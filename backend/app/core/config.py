from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/cybernote.db"

    # JWT
    secret_key: str = "change-me-to-a-random-string"
    access_token_expire_minutes: int = 1440

    # Auth
    auth_mode: str = "none"  # "none" | "jwt"

    # CORS
    allowed_origins: str = "*"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # App
    app_name: str = "CyberNote"
    app_version: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

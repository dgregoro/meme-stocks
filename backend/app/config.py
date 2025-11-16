from __future__ import annotations

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Defaults are chosen to be safe for local development.
    Secrets (API keys, etc.) must be provided via environment or .env file.
    """

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "sqlite:///../data/app.db"

    # Reddit API credentials
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "meme-stocks-app/0.1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings.

    Raises ValidationError explicitly if environment variables are invalid,
    rather than silently falling back.
    """

    try:
        return Settings()
    except ValidationError as exc:  # pragma: no cover - defensive, but tested via unit tests
        # Re-raise to ensure FastAPI startup fails loudly if config is invalid.
        raise exc

from __future__ import annotations

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Defaults are chosen to be safe for local development.
    Secrets (API keys, etc.) must be provided via environment or .env file.
    """

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    log_file: str = "logs/app.log"  # Third-party noise (yfinance, etc.) written here, not terminal

    database_url: str = "sqlite:///./data/app.db"

    # Reddit API credentials
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "meme-stocks-app/0.1"

    # Analysis thresholds (can be tuned via environment)
    sentiment_positive_threshold: float = 0.3
    sentiment_negative_threshold: float = -0.2
    sentiment_positive_keywords: str = "buy,moon,hold,bullish,gains,profit,long"
    sentiment_negative_keywords: str = "sell,crash,bearish,loss,dump,scam,short"
    volume_spike_threshold: float = 2.0
    price_movement_threshold_pct: float = 5.0
    sentiment_shift_threshold: float = 0.3

    # Analysis weights and windows
    analysis_sentiment_weight: float = 0.6  # Weight for sentiment in composite score
    analysis_trend_weight: float = 0.4  # Weight for trend in composite score
    sentiment_window_hours: int = 24  # Window for sentiment aggregation
    reddit_max_age_days: int = 2  # Max age of Reddit posts to fetch
    price_history_days: int = 30  # Days of price history for analysis

    # CORS
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Scheduling configuration
    reddit_collection_interval_minutes: int = 60  # Collect Reddit data every hour
    price_collection_interval_minutes: int = 15  # Collect price data every 15 minutes
    notification_check_interval_minutes: int = 30  # Check for notifications every 30 minutes
    daily_analysis_hour: int = 16  # Run daily analysis at 4 PM (16:00) local time
    reddit_subreddits: str = "wallstreetbets,stocks,investing"  # Comma-separated list
    enable_catch_up: bool = True  # Run missed jobs on startup

    # SEC EDGAR (requires User-Agent; use contact email for compliance)
    sec_user_agent: str = "MemeStocksApp/1.0 (contact@example.com)"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


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

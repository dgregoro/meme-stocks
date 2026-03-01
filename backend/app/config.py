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

    # Optional: use HuggingFace ticker NER model for extra candidates (default off)
    enable_ticker_ner: bool = False

    # Ticker disambiguation (ticker vs common word)
    ticker_disambiguation_enabled: bool = True
    ticker_disambiguation_return_maybe: bool = False
    ticker_disambiguation_window_tokens: int = 5
    # Comma-separated list of high-collision tickers (tune without code changes)
    ticker_high_collision_symbols: str = (
        "A,IT,OR,ON,ALL,ONE,RUN,FOR,LOVE,OPEN,REAL,HOPE,RIDE,SAVE,SOLO,TALK,WORK,PLAN,LIVE,PLAY"
    )

    # Alpaca market data (intraday minute bars)
    # Free plan: full-market SIP is delayed; use delayed_sip (15-min delay).
    # Do not query the last ~15 minutes when using delayed SIP on free—requests can fail.
    # Real-time on free is IEX-only, not consolidated; we use delayed_sip for broad market.
    alpaca_data_feed: str = "delayed_sip"
    alpaca_free_plan_mode: bool = True
    alpaca_sip_delay_minutes: int = 15
    alpaca_end_time_safety_minutes: int = 20  # end = now - this (default 20 > 15 for clock skew)
    alpaca_api_key_id: str | None = None
    alpaca_api_secret_key: str | None = None
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    # Intraday ingestion
    intraday_ingestion_enabled: bool = False
    intraday_symbols_batch_size: int = 200
    intraday_lookback_days: int = 30
    intraday_universe_mode: str = "tracked"  # tracked | top_liquidity | all_active (future)
    intraday_feature_store_root: str = "data/intraday"
    intraday_max_pages_per_batch: int = 100
    intraday_interval_minutes: int = 15  # scheduler interval
    # Feature store: when True, read_bars raises if any partition file is unreadable
    feature_store_strict_reads: bool = False

    # Intraday ingestion governance: global lock to prevent overlapping runs (scheduler + API)
    intraday_lock_enabled: bool = True
    intraday_lock_ttl_seconds: int = 1800  # 30 min; must be longer than worst-case run
    intraday_lock_heartbeat_seconds: int = 60
    intraday_lock_name: str = "intraday_ingestion"

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

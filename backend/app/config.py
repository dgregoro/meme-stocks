from __future__ import annotations

from functools import lru_cache

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Defaults are chosen to be safe for local development.
    Secrets (API keys, etc.) must be provided via environment or .env file.
    """

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    app_version: str = "dev"  # Set at build (APP_VERSION) for deploy health validation
    log_file: str = "logs/app.log"  # Third-party noise (yfinance, etc.) written here, not terminal

    database_url: str = "sqlite:///./data/app.db"

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
    sentiment_window_hours: int = 24  # Reserved for future sentiment sources
    price_history_days: int = 30  # Days of price history for analysis

    # RSI (Relative Strength Index) — Phase 2.3 (see pattern_analyzer)
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # SMA uptrend treated as breakout only if latest volume confirms (Phase 2.4)
    pattern_breakout_require_volume: bool = True
    pattern_breakout_volume_ratio: float = 1.0  # latest / mean(prior volumes); 1.0 = at least average

    # Combined signal alerts (Phase 2, Task 2.5)
    combined_signal_weight_sentiment: float = 2.0
    combined_signal_weight_price: float = 2.0
    combined_signal_weight_volume: float = 1.0
    combined_signal_weight_rsi: float = 1.0
    combined_signal_threshold: float = 4.0
    combined_signal_alerts_only: bool = False

    # CORS
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Scheduling configuration
    price_collection_interval_minutes: int = 15  # Collect price data every 15 minutes
    notification_check_interval_minutes: int = 30  # Check for notifications every 30 minutes
    daily_analysis_hour: int = 16  # Run daily analysis at 4 PM (16:00) local time
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
    # Historical bars endpoint rejects delayed_sip (400 invalid feed); use iex for bars.
    # alpaca_data_feed names logical/streaming feed; historical bars use alpaca_bars_feed.
    alpaca_data_feed: str = "delayed_sip"
    alpaca_bars_feed: str = "iex"  # Feed for historical bars; iex works on free plan
    alpaca_free_plan_mode: bool = True
    alpaca_sip_delay_minutes: int = 15
    alpaca_end_time_safety_minutes: int = 20  # end = now - this (default 20 > 15 for clock skew)
    alpaca_api_key_id: str | None = None
    alpaca_api_secret_key: str | None = None
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    # 200 req/min = 1 req per 0.3s; 0.35s keeps us under. 0 = no throttle.
    alpaca_min_request_interval_seconds: float = 0.35
    # Intraday ingestion
    intraday_ingestion_enabled: bool = False
    intraday_symbols_batch_size: int = 200
    intraday_max_symbols_per_run: int = 500  # Cap per run; 0 = unlimited. Prevents hammering API when config is wrong.
    intraday_lookback_days: int = 30
    intraday_universe_mode: str = "tracked"  # tracked | top_liquidity | all_active (future)
    intraday_feature_store_root: str = "data/intraday"
    intraday_max_pages_per_batch: int = 100
    intraday_interval_minutes: int = 15  # scheduler interval
    intraday_group_span_hours: float = 1.0  # max span within a start-window group (avoids refetch duplication)
    # Feature store: when True, read_bars raises if any partition file is unreadable
    feature_store_strict_reads: bool = False

    # Intraday ingestion governance: global lock to prevent overlapping runs (scheduler + API)
    intraday_lock_enabled: bool = True
    intraday_lock_ttl_seconds: int = 1800  # 30 min; must be longer than worst-case run
    intraday_lock_heartbeat_seconds: int = 60
    intraday_lock_name: str = "intraday_ingestion"

    # Causal / lead-lag analysis: minimum buckets for valid analysis
    causal_min_buckets_15m: int = 200
    causal_min_buckets_1h: int = 200
    causal_min_buckets_1d: int = 60

    # Leader-follower signal detection (003-leader-follower-signal-detection)
    leader_follower_enabled: bool = False
    leader_return_threshold_pct: float = 5.0
    leader_volume_spike_threshold: float = 1.5
    leader_follower_cooldown_days: int = 1
    follower_move_threshold_pct: float = 3.0
    leader_follower_job_hour: int = 17
    leader_follower_strength_weight_return: float = 0.6
    leader_follower_strength_weight_volume: float = 0.4
    leader_follower_norm_return_cap_pct: float = 15.0
    leader_follower_norm_volume_cap: float = 4.0

    # Leader threshold calibration and bootstrap debugging (006)
    leader_follower_debug_mode: bool = False
    leader_return_threshold_pct_debug: float = 3.0
    leader_volume_spike_threshold_debug: float = 1.2

    # Leader-follower signal evaluation (007)
    leader_follower_evaluation_horizons: str = "1,3,5"  # Comma-separated trading-day forward horizons
    leader_follower_evaluation_overlap_window_days: int = 5  # Window for duplicate/overlap count

    # Leader-follower pair filtering and ranking (009)
    leader_follower_pair_min_signal_count: int = 2  # Min signals for pair to be included
    leader_follower_pair_min_avg_return_1d: float = 0.0  # Min 1d avg return (pct); 0 = allow positive
    leader_follower_pair_min_win_rate_1d: float = 0.5  # Min 1d win rate; exclude <50%
    enable_pair_filtering_for_signals: bool = False  # When true, restrict signal gen to filtered pairs
    leader_follower_pair_filter_lookback_days: int = 90  # Window for evaluation when filtering signals

    # Walk-forward optimization (010): cap Cartesian product size (research CLI)
    leader_follower_optimization_max_grid_points: int = 256

    # Rolling robustness (012): cap splits × candidates (research CLI)
    leader_follower_robustness_max_evaluations: int = 5000

    # Leader-follower regime gate (014): benchmarks merged into Alpaca replay backfill so SPY bars exist for gating
    leader_follower_regime_backfill_symbols: str = "SPY"

    # Volume spike research (015): daily volume vs rolling baseline; distinct from analysis volume_spike_threshold
    volume_spike_research_baseline_window_days: int = 20
    volume_spike_research_baseline_statistic: str = "median"  # median | mean
    volume_spike_research_ratio_threshold: float = 3.0
    volume_spike_research_flat_band_pct: float = 0.5  # spike_up if return >= band; spike_down if <= -band
    volume_spike_research_horizons: str = "1,3,5"
    volume_spike_research_min_close: float = 0.0  # 0 = disabled
    volume_spike_research_min_baseline_volume: float = 0.0  # 0 = disabled

    # Daily-frequency strategy research (STRATEGY_EXPLORATION S1/S2); see docs/STRATEGY_TESTING_PLAN.md
    daily_strategy_realized_vol_window: int = 10
    daily_strategy_volume_z_window: int = 20
    daily_strategy_regime_lookback_days: int = 252
    daily_strategy_regime_min_prior_days: int = 60
    daily_strategy_gap_ma_window: int = 20
    daily_strategy_horizons: str = "1,5,10"
    # Automated merit report (evaluate daily-strategy s1-merit); align with SIGNAL_EVALUATION_CHECKLIST
    daily_strategy_merit_min_events_per_regime: int = 50
    daily_strategy_merit_concentration_top5_max_pct: float = 0.65
    # Optional auto-fetch for evaluate daily-strategy --ensure-data (019 preflight)
    daily_strategy_ensure_data_prior_calendar_days: int = 580
    daily_strategy_ensure_data_end_buffer_calendar_days: int = 45
    daily_strategy_ensure_data_max_symbols: int = 64
    # When True, s1-merit / s2-merit / eval-bundle persist full JSON to daily_strategy_merit_runs
    daily_strategy_merit_persist_runs: bool = True

    # Daily-frequency S3: VIX vs VIX3M term structure (021); Yahoo indices + expanding quantile regimes
    s3_vix_symbol: str = "^VIX"
    s3_vix3m_symbol: str = "^VIX3M"
    s3_feature_mode: str = "spread"  # spread | ratio
    s3_ratio_denominator_floor: float = 0.01
    s3_regime_min_history_days: int = 252
    s3_regime_n_buckets: int = 4
    s3_macro_backfill_calendar_buffer_days: int = 420

    # Daily-frequency S4: calendar flags (022); calendar month boundaries, not NYSE holiday calendar
    s4_include_opex_week: bool = True
    s4_include_calendar_month_end: bool = True
    s4_include_quarter_end_calendar: bool = True

    # Daily-frequency S5: cross-sectional return dispersion panel (023); expanding quantile regimes
    s5_min_symbols_cross_section: int = 10
    s5_regime_min_history_days: int = 252
    s5_regime_n_buckets: int = 4
    s5_load_buffer_calendar_days: int = 400

    # Default round-trip cost for documentation / ResearchRunEnvelope (actual sims use their own fields)
    research_default_round_trip_cost_bps: float = 10.0

    # Extreme move research (016): large daily close-to-close return; mean-reversion hypothesis
    extreme_move_up_threshold_pct: float = 5.0
    extreme_move_down_threshold_pct: float = 5.0
    extreme_move_research_horizons: str = "1,3,5"
    extreme_move_research_min_close: float = 0.0  # 0 = disabled
    # 017: volume context uses same rolling baseline window/stat as volume_spike_research_*
    extreme_move_context_volume_high_ratio: float = 1.5
    extreme_move_context_volume_extreme_ratio: float = 3.0

    # Research API: dataset output and allowed paths for experiments
    research_dataset_dir: str = (
        "data/research"  # Output dir for build-dataset; experiments accept only paths under this
    )
    # S&P Composite 1500 cap-filter CLI: default CSV path (repo-relative); see data/research/universes/README.md
    research_sp1500_constituents_csv: str = "data/research/universes/sp_composite_1500_constituents.csv"
    # Optional hand-edited JSON for ``strategies list`` evidence column; see example in data/research/
    research_strategy_evidence_status_json: str = "data/research/strategy_evidence_status.json"

    # Market clock (intraday ingestion, status dashboards)
    market_timezone: str = "America/New_York"
    market_close_hour_local: int = 16  # Local hour when market closes
    market_close_minute_local: int = 0  # Local minute when market closes

    @field_validator("rsi_period")
    @classmethod
    def rsi_period_at_least_two(cls, v: int) -> int:
        if v < 2:
            raise ValueError("rsi_period must be >= 2")
        return v

    @field_validator("rsi_overbought", "rsi_oversold")
    @classmethod
    def rsi_threshold_0_100(cls, v: float) -> float:
        if not 0 <= v <= 100:
            raise ValueError("RSI thresholds must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def rsi_oversold_less_than_overbought(self) -> "Settings":
        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError("rsi_oversold must be < rsi_overbought")
        return self

    @field_validator("pattern_breakout_volume_ratio")
    @classmethod
    def pattern_breakout_volume_ratio_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("pattern_breakout_volume_ratio must be > 0")
        return v

    model_config = SettingsConfigDict(
        # Only load .env from cwd (repo root). Tests run without it.
        # For containers: use deployment/.env via compose env_file; vars are injected, not loaded here.
        env_file=".env",
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

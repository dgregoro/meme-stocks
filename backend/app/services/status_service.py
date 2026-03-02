"""Service for system/data collection status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_daily_feature import RedditDailyFeature
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock


JobStatusValue = Literal["ran", "never"]


@dataclass(frozen=True)
class JobStatusResult:
    job_id: str
    schedule: str | None
    last_run_utc: datetime | None
    last_status: JobStatusValue
    last_error: str | None
    duration_seconds: float | None


@dataclass(frozen=True)
class RedditCollectionStatusResult:
    posts_last_1h: int
    posts_last_24h: int
    mentions_last_1h: int
    mentions_last_24h: int
    newest_post_posted_at_utc: datetime | None
    newest_post_collected_at_utc: datetime | None
    oldest_post_collected_at_utc: datetime | None


@dataclass(frozen=True)
class PriceCollectionStatusResult:
    newest_price_date: date | None
    price_rows_last_7d: int
    price_rows_last_30d: int


@dataclass(frozen=True)
class DailyFeatureStatusResult:
    newest_trading_day: date | None
    rows_last_7d: int
    rows_last_30d: int


@dataclass(frozen=True)
class HealthResult:
    reddit: Literal["ok", "stale", "empty"]
    prices: Literal["ok", "stale", "empty"]
    daily_features: Literal["ok", "stale", "empty"]
    jobs: Literal["ok", "warning"]
    reddit_stale_after_minutes: int
    prices_stale_after_days: int
    features_stale_after_days: int


@dataclass(frozen=True)
class SymbolStalenessResult:
    symbol: str
    last_reddit_collected_at_utc: datetime | None
    last_price_date: date | None
    last_daily_feature_day: date | None
    stale_reasons: list[str]


@dataclass(frozen=True)
class CollectionStatusResult:
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatusResult]
    reddit: RedditCollectionStatusResult
    prices: PriceCollectionStatusResult
    daily_features: DailyFeatureStatusResult
    health: HealthResult


def get_collection_status(db: Session) -> CollectionStatusResult:
    """Return snapshot of collection/ingestion status."""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    market_tz = ZoneInfo(settings.market_timezone)
    market_now = now_utc.astimezone(market_tz)
    market_today = market_now.date()

    jobs = _build_job_statuses(db, settings, now_utc)
    reddit = _build_reddit_status(db, now_utc)
    prices = _build_price_status(db, market_today)
    daily_features = _build_daily_feature_status(db, market_today)

    health = _compute_health(settings, now_utc, market_today, reddit, prices, daily_features, jobs)

    return CollectionStatusResult(
        server_time_utc=now_utc,
        market_time_local=market_now,
        jobs=jobs,
        reddit=reddit,
        prices=prices,
        daily_features=daily_features,
        health=health,
    )


def _build_job_statuses(db: Session, settings: object, now_utc: datetime) -> list[JobStatusResult]:
    """Build simple job status list using JobExecutionRepository.

    Schema only tracks last_run_at; we treat that as last_success_utc with no duration/error.
    """
    job_repo = JobExecutionRepository(db)

    # Known jobs in this app; schedules are approximate human-readable descriptions.
    job_definitions: dict[str, str | None] = {
        "reddit_collection": f"every {getattr(settings, 'reddit_collection_interval_minutes', 60)} min",
        "price_collection": f"every {getattr(settings, 'price_collection_interval_minutes', 15)} min",
        "daily_analysis": f"daily at {getattr(settings, 'daily_analysis_hour', 16):02d}:00",
        "notification_check": f"every {getattr(settings, 'notification_check_interval_minutes', 30)} min",
        "reddit_daily_features": f"daily at {getattr(settings, 'reddit_daily_features_job_hour', 17):02d}:00",
        "intraday_ingestion": (
            f"every {getattr(settings, 'intraday_interval_minutes', 15)} min"
            if getattr(settings, "intraday_ingestion_enabled", False)
            else None
        ),
    }

    results: list[JobStatusResult] = []
    for job_id, schedule in sorted(job_definitions.items()):
        if job_id == "intraday_ingestion" and not getattr(settings, "intraday_ingestion_enabled", False):
            continue
        last_run = job_repo.get_last_run(job_id)
        if last_run is None:
            status: JobStatusValue = "never"
        else:
            status = "ran"

        results.append(
            JobStatusResult(
                job_id=job_id,
                schedule=schedule,
                last_run_utc=last_run,
                last_status=status,
                last_error=None,
                duration_seconds=None,
            )
        )

    return results


def _build_reddit_status(db: Session, now_utc: datetime) -> RedditCollectionStatusResult:
    one_hour_ago = now_utc - timedelta(hours=1)
    day_ago = now_utc - timedelta(hours=24)

    # Posts counts by collected_at
    posts_last_1h = (
        db.execute(
            select(func.count()).select_from(RedditPost).where(RedditPost.collected_at >= one_hour_ago)
        ).scalar_one()
        or 0
    )
    posts_last_24h = (
        db.execute(select(func.count()).select_from(RedditPost).where(RedditPost.collected_at >= day_ago)).scalar_one()
        or 0
    )

    # Mentions counts via join
    mentions_last_1h = (
        db.execute(
            select(func.count())
            .select_from(RedditSymbolMention)
            .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
            .where(RedditPost.collected_at >= one_hour_ago)
        ).scalar_one()
        or 0
    )
    mentions_last_24h = (
        db.execute(
            select(func.count())
            .select_from(RedditSymbolMention)
            .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
            .where(RedditPost.collected_at >= day_ago)
        ).scalar_one()
        or 0
    )

    newest_post_posted_at = db.execute(select(func.max(RedditPost.posted_at))).scalar_one()
    newest_post_collected_at = db.execute(select(func.max(RedditPost.collected_at))).scalar_one()
    oldest_post_collected_at = db.execute(select(func.min(RedditPost.collected_at))).scalar_one()

    return RedditCollectionStatusResult(
        posts_last_1h=int(posts_last_1h),
        posts_last_24h=int(posts_last_24h),
        mentions_last_1h=int(mentions_last_1h),
        mentions_last_24h=int(mentions_last_24h),
        newest_post_posted_at_utc=newest_post_posted_at,
        newest_post_collected_at_utc=newest_post_collected_at,
        oldest_post_collected_at_utc=oldest_post_collected_at,
    )


def _build_price_status(db: Session, today: date) -> PriceCollectionStatusResult:
    newest_price_date = db.execute(select(func.max(PriceData.date))).scalar_one()

    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    rows_last_7d = (
        db.execute(select(func.count()).select_from(PriceData).where(PriceData.date >= seven_days_ago)).scalar_one()
        or 0
    )
    rows_last_30d = (
        db.execute(select(func.count()).select_from(PriceData).where(PriceData.date >= thirty_days_ago)).scalar_one()
        or 0
    )

    return PriceCollectionStatusResult(
        newest_price_date=newest_price_date,
        price_rows_last_7d=int(rows_last_7d),
        price_rows_last_30d=int(rows_last_30d),
    )


def _build_daily_feature_status(db: Session, today: date) -> DailyFeatureStatusResult:
    newest_trading_day = db.execute(select(func.max(RedditDailyFeature.trading_day))).scalar_one()

    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    rows_last_7d = (
        db.execute(
            select(func.count()).select_from(RedditDailyFeature).where(RedditDailyFeature.trading_day >= seven_days_ago)
        ).scalar_one()
        or 0
    )
    rows_last_30d = (
        db.execute(
            select(func.count())
            .select_from(RedditDailyFeature)
            .where(RedditDailyFeature.trading_day >= thirty_days_ago)
        ).scalar_one()
        or 0
    )

    return DailyFeatureStatusResult(
        newest_trading_day=newest_trading_day,
        rows_last_7d=int(rows_last_7d),
        rows_last_30d=int(rows_last_30d),
    )


def _compute_health(
    settings: object,
    now_utc: datetime,
    market_today: date,
    reddit: RedditCollectionStatusResult,
    prices: PriceCollectionStatusResult,
    daily_features: DailyFeatureStatusResult,
    jobs: list[JobStatusResult],
) -> HealthResult:
    """Compute simple OK/STALE/EMPTY health flags plus thresholds used."""
    reddit_threshold_minutes = 120
    prices_threshold_days = 2
    features_threshold_days = 2

    # Reddit health
    newest_collected = reddit.newest_post_collected_at_utc
    if newest_collected is None:
        reddit_health: Literal["ok", "stale", "empty"] = "empty"
    else:
        # Normalize to aware UTC before subtraction
        if newest_collected.tzinfo is None:
            newest_collected = newest_collected.replace(tzinfo=timezone.utc)
        diff_minutes = (now_utc - newest_collected).total_seconds() / 60.0
        reddit_health = "stale" if diff_minutes > reddit_threshold_minutes else "ok"

    # Prices health
    if prices.newest_price_date is None:
        prices_health: Literal["ok", "stale", "empty"] = "empty"
    else:
        diff_days = (market_today - prices.newest_price_date).days
        prices_health = "stale" if diff_days > prices_threshold_days else "ok"

    # Daily features health
    if daily_features.newest_trading_day is None:
        features_health: Literal["ok", "stale", "empty"] = "empty"
    else:
        diff_days = (market_today - daily_features.newest_trading_day).days
        features_health = "stale" if diff_days > features_threshold_days else "ok"

    # Jobs health: warn if any job never ran or last_run is older than a simple threshold.
    jobs_health: Literal["ok", "warning"] = "ok"
    for job in jobs:
        if job.last_status == "never":
            jobs_health = "warning"
            break
        if job.last_run_utc is None:
            continue
        # Per-job stale threshold in minutes (approximate; 3x configured interval or 36h for daily jobs).
        stale_minutes: int
        if job.job_id in ("reddit_collection", "price_collection", "notification_check", "intraday_ingestion"):
            interval = getattr(
                settings,
                {
                    "reddit_collection": "reddit_collection_interval_minutes",
                    "price_collection": "price_collection_interval_minutes",
                    "notification_check": "notification_check_interval_minutes",
                    "intraday_ingestion": "intraday_interval_minutes",
                }[job.job_id],
                60,
            )
            stale_minutes = int(interval) * 3
        else:
            # daily jobs
            stale_minutes = 36 * 60

        if (now_utc - job.last_run_utc).total_seconds() / 60.0 > stale_minutes:
            jobs_health = "warning"
            break

    return HealthResult(
        reddit=reddit_health,
        prices=prices_health,
        daily_features=features_health,
        jobs=jobs_health,
        reddit_stale_after_minutes=reddit_threshold_minutes,
        prices_stale_after_days=prices_threshold_days,
        features_stale_after_days=features_threshold_days,
    )


def get_stale_symbols(db: Session, limit: int) -> list[SymbolStalenessResult]:
    """Return top-N stalest symbols based on Reddit, price, and daily features."""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    market_tz = ZoneInfo(settings.market_timezone)
    market_today = now_utc.astimezone(market_tz).date()

    reddit_threshold_minutes = 120
    prices_threshold_days = 2
    features_threshold_days = 2

    symbols = [row[0] for row in db.execute(select(Stock.symbol)).all()]
    if not symbols:
        return []

    # Last Reddit collected_at per symbol
    reddit_rows = db.execute(
        select(RedditSymbolMention.symbol, func.max(RedditPost.collected_at))
        .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
        .group_by(RedditSymbolMention.symbol)
    ).all()
    last_reddit_by_symbol: dict[str, datetime | None] = {sym: ts for sym, ts in reddit_rows}

    # Last price date per symbol
    price_rows = db.execute(
        select(PriceData.stock_symbol, func.max(PriceData.date)).group_by(PriceData.stock_symbol)
    ).all()
    last_price_by_symbol: dict[str, date | None] = {sym: d for sym, d in price_rows}

    # Last daily feature trading_day per symbol
    feature_rows = db.execute(
        select(RedditDailyFeature.symbol, func.max(RedditDailyFeature.trading_day)).group_by(RedditDailyFeature.symbol)
    ).all()
    last_feature_by_symbol: dict[str, date | None] = {sym: d for sym, d in feature_rows}

    stale: list[tuple[SymbolStalenessResult, date]] = []
    far_past = date(1970, 1, 1)

    for symbol in symbols:
        last_reddit = last_reddit_by_symbol.get(symbol)
        last_price = last_price_by_symbol.get(symbol)
        last_feature = last_feature_by_symbol.get(symbol)

        reasons: list[str] = []
        if last_reddit is None:
            reasons.append("no_reddit")
        else:
            diff_minutes = (now_utc - last_reddit).total_seconds() / 60.0
            if diff_minutes > reddit_threshold_minutes:
                reasons.append("reddit_stale")

        if last_price is None:
            reasons.append("no_price")
        else:
            diff_days = (market_today - last_price).days
            if diff_days > prices_threshold_days:
                reasons.append("price_stale")

        if last_feature is None:
            reasons.append("no_daily_features")
        else:
            diff_days = (market_today - last_feature).days
            if diff_days > features_threshold_days:
                reasons.append("daily_features_stale")

        if not reasons:
            continue

        # Use the oldest of the available dates as a rough staleness score (earlier = worse).
        candidate_dates: list[date] = []
        if last_reddit is not None:
            candidate_dates.append(last_reddit.date())
        if last_price is not None:
            candidate_dates.append(last_price)
        if last_feature is not None:
            candidate_dates.append(last_feature)
        score_date = min(candidate_dates) if candidate_dates else far_past

        stale.append(
            (
                SymbolStalenessResult(
                    symbol=symbol,
                    last_reddit_collected_at_utc=last_reddit,
                    last_price_date=last_price,
                    last_daily_feature_day=last_feature,
                    stale_reasons=reasons,
                ),
                score_date,
            )
        )

    stale.sort(key=lambda item: item[1])
    return [s for s, _ in stale[:limit]]

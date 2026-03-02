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


JobStatusValue = Literal["success", "failure", "running", "never"]


@dataclass(frozen=True)
class JobStatusResult:
    job_id: str
    schedule: str | None
    last_start_utc: datetime | None
    last_end_utc: datetime | None
    last_success_utc: datetime | None
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
class CollectionStatusResult:
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatusResult]
    reddit: RedditCollectionStatusResult
    prices: PriceCollectionStatusResult
    daily_features: DailyFeatureStatusResult


def get_collection_status(db: Session) -> CollectionStatusResult:
    """Return snapshot of collection/ingestion status."""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    market_tz = ZoneInfo(settings.market_timezone)
    market_now = now_utc.astimezone(market_tz)

    jobs = _build_job_statuses(db, settings)
    reddit = _build_reddit_status(db, now_utc)
    prices = _build_price_status(db, now_utc.date())
    daily_features = _build_daily_feature_status(db, now_utc.date())

    return CollectionStatusResult(
        server_time_utc=now_utc,
        market_time_local=market_now,
        jobs=jobs,
        reddit=reddit,
        prices=prices,
        daily_features=daily_features,
    )


def _build_job_statuses(db: Session, settings: object) -> list[JobStatusResult]:
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
            last_success = None
        else:
            status = "success"
            last_success = last_run

        results.append(
            JobStatusResult(
                job_id=job_id,
                schedule=schedule,
                last_start_utc=last_run,
                last_end_utc=last_run,
                last_success_utc=last_success,
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
        db.execute(
            select(func.count()).select_from(RedditPost).where(RedditPost.collected_at >= day_ago)
        ).scalar_one()
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

    newest_post_posted_at = (
        db.execute(select(func.max(RedditPost.posted_at))).scalar_one()
    )
    newest_post_collected_at = (
        db.execute(select(func.max(RedditPost.collected_at))).scalar_one()
    )
    oldest_post_collected_at = (
        db.execute(select(func.min(RedditPost.collected_at))).scalar_one()
    )

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
        db.execute(
            select(func.count())
            .select_from(PriceData)
            .where(PriceData.date >= seven_days_ago)
        ).scalar_one()
        or 0
    )
    rows_last_30d = (
        db.execute(
            select(func.count())
            .select_from(PriceData)
            .where(PriceData.date >= thirty_days_ago)
        ).scalar_one()
        or 0
    )

    return PriceCollectionStatusResult(
        newest_price_date=newest_price_date,
        price_rows_last_7d=int(rows_last_7d),
        price_rows_last_30d=int(rows_last_30d),
    )


def _build_daily_feature_status(db: Session, today: date) -> DailyFeatureStatusResult:
    newest_trading_day = db.execute(
        select(func.max(RedditDailyFeature.trading_day))
    ).scalar_one()

    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    rows_last_7d = (
        db.execute(
            select(func.count())
            .select_from(RedditDailyFeature)
            .where(RedditDailyFeature.trading_day >= seven_days_ago)
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


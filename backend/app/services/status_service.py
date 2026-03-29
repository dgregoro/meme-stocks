"""Service for system/data collection status (price data and jobs; Reddit removed)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from backend.app.config import get_settings
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock


def _as_utc_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _minutes_since(now_utc: datetime, dt: datetime | None) -> float | None:
    dt2 = _as_utc_aware(dt)
    if dt2 is None:
        return None
    return (now_utc - dt2).total_seconds() / 60.0


JobStatusValue = Literal["ran", "never"]


@dataclass(frozen=True)
class JobStatusResult:
    job_id: str
    schedule: str | None
    last_run_utc: datetime | None
    last_success_utc: datetime | None
    last_status: JobStatusValue
    last_error: str | None
    duration_seconds: float | None
    last_run_summary: str | None = None
    last_success_summary: str | None = None


@dataclass(frozen=True)
class PriceCollectionStatusResult:
    newest_price_date: date | None
    price_rows_last_7d: int
    price_rows_last_30d: int


@dataclass(frozen=True)
class HealthResult:
    prices: Literal["ok", "stale", "empty"]
    jobs: Literal["ok", "warning"]
    prices_stale_after_days: int


@dataclass(frozen=True)
class SymbolStalenessResult:
    symbol: str
    last_price_date: date | None
    stale_reasons: list[str]


@dataclass(frozen=True)
class CollectionStatusResult:
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatusResult]
    prices: PriceCollectionStatusResult
    health: HealthResult


def get_collection_status(db: Session) -> CollectionStatusResult:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    market_tz = ZoneInfo(settings.market_timezone)
    market_now = now_utc.astimezone(market_tz)
    market_today = market_now.date()

    jobs = _build_job_statuses(db, settings, now_utc)
    prices = _build_price_status(db, market_today)
    health = _compute_health(settings, now_utc, market_today, prices, jobs)

    return CollectionStatusResult(
        server_time_utc=now_utc,
        market_time_local=market_now,
        jobs=jobs,
        prices=prices,
        health=health,
    )


def _build_job_statuses(db: Session, settings: object, now_utc: datetime) -> list[JobStatusResult]:
    job_repo = JobExecutionRepository(db)
    job_definitions: dict[str, str | None] = {
        "price_collection": f"every {getattr(settings, 'price_collection_interval_minutes', 15)} min",
        "daily_analysis": f"daily at {getattr(settings, 'daily_analysis_hour', 16):02d}:00",
        "notification_check": f"every {getattr(settings, 'notification_check_interval_minutes', 30)} min",
        "intraday_ingestion": (
            f"every {getattr(settings, 'intraday_interval_minutes', 15)} min"
            if getattr(settings, "intraday_ingestion_enabled", False)
            else None
        ),
    }
    if getattr(settings, "leader_follower_enabled", False):
        job_definitions["leader_follower_detection"] = (
            f"daily at {getattr(settings, 'leader_follower_job_hour', 17):02d}:00"
        )

    results: list[JobStatusResult] = []
    for job_id, schedule in sorted(job_definitions.items()):
        if job_id == "intraday_ingestion" and not getattr(settings, "intraday_ingestion_enabled", False):
            continue
        last_run = job_repo.get_last_run(job_id)
        last_success = job_repo.get_last_success(job_id)
        status: JobStatusValue = "never" if last_run is None else "ran"
        results.append(
            JobStatusResult(
                job_id=job_id,
                schedule=schedule,
                last_run_utc=last_run,
                last_success_utc=last_success,
                last_status=status,
                last_error=None,
                duration_seconds=None,
                last_run_summary=job_repo.get_last_run_summary(job_id),
                last_success_summary=job_repo.get_last_success_summary(job_id),
            )
        )
    return results


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


def _compute_health(
    settings: object,
    now_utc: datetime,
    market_today: date,
    prices: PriceCollectionStatusResult,
    jobs: list[JobStatusResult],
) -> HealthResult:
    prices_threshold_days = 2
    if prices.newest_price_date is None:
        prices_health: Literal["ok", "stale", "empty"] = "empty"
    else:
        diff_days = (market_today - prices.newest_price_date).days
        prices_health = "stale" if diff_days > prices_threshold_days else "ok"

    jobs_health: Literal["ok", "warning"] = "ok"
    for job in jobs:
        if job.last_status == "never":
            jobs_health = "warning"
            break
        minutes_since_run = _minutes_since(now_utc, job.last_run_utc)
        if minutes_since_run is None:
            continue
        if job.job_id in ("price_collection", "notification_check", "intraday_ingestion"):
            interval = getattr(
                settings,
                {
                    "price_collection": "price_collection_interval_minutes",
                    "notification_check": "notification_check_interval_minutes",
                    "intraday_ingestion": "intraday_interval_minutes",
                }[job.job_id],
                60,
            )
            stale_minutes = int(interval) * 3
        else:
            stale_minutes = 36 * 60
        if minutes_since_run > stale_minutes:
            jobs_health = "warning"
            break

    return HealthResult(
        prices=prices_health,
        jobs=jobs_health,
        prices_stale_after_days=prices_threshold_days,
    )


def get_stale_symbols(db: Session, limit: int) -> list[SymbolStalenessResult]:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    market_tz = ZoneInfo(settings.market_timezone)
    market_today = now_utc.astimezone(market_tz).date()
    prices_threshold_days = 2

    symbols = [row[0] for row in db.execute(select(Stock.symbol)).all()]
    if not symbols:
        return []

    price_rows = db.execute(
        select(PriceData.stock_symbol, func.max(PriceData.date)).group_by(PriceData.stock_symbol)
    ).all()
    last_price_by_symbol: dict[str, date | None] = {sym: d for sym, d in price_rows}

    stale: list[tuple[SymbolStalenessResult, date]] = []
    far_past = date(1970, 1, 1)

    for symbol in symbols:
        last_price = last_price_by_symbol.get(symbol)
        reasons: list[str] = []
        if last_price is None:
            reasons.append("no_price")
        else:
            diff_days = (market_today - last_price).days
            if diff_days > prices_threshold_days:
                reasons.append("price_stale")
        if not reasons:
            continue
        score_date = last_price if last_price is not None else far_past
        stale.append(
            (
                SymbolStalenessResult(
                    symbol=symbol,
                    last_price_date=last_price,
                    stale_reasons=reasons,
                ),
                score_date,
            )
        )
    stale.sort(key=lambda item: item[1])
    return [s for s, _ in stale[:limit]]

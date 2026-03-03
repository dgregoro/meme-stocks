from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.job_run_history import JobRunHistory
from backend.app.services.status_service import (
    CollectionStatusResult,
    DailyFeatureStatusResult,
    HealthResult,
    JobStatusResult,
    PriceCollectionStatusResult,
    RedditCollectionStatusResult,
    SymbolStalenessResult,
    get_collection_status,
    get_stale_symbols,
)
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import DataAccessError


router = APIRouter(prefix="/api/status", tags=["status"])


class JobStatus(BaseModel):
    job_id: str
    schedule: str | None = None
    last_run_utc: datetime | None = None
    last_success_utc: datetime | None = None
    last_status: Literal["ran", "never"]
    last_error: str | None = None
    duration_seconds: float | None = None

    model_config = ConfigDict(from_attributes=True)


class RedditCollectionStatus(BaseModel):
    posts_last_1h: int
    posts_last_24h: int
    mentions_last_1h: int
    mentions_last_24h: int
    newest_post_posted_at_utc: datetime | None = None
    newest_post_collected_at_utc: datetime | None = None
    oldest_post_collected_at_utc: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PriceCollectionStatus(BaseModel):
    newest_price_date: datetime | None = None
    price_rows_last_7d: int
    price_rows_last_30d: int

    model_config = ConfigDict(from_attributes=True)


class DailyFeatureStatus(BaseModel):
    newest_trading_day: datetime | None = None
    rows_last_7d: int
    rows_last_30d: int

    model_config = ConfigDict(from_attributes=True)


class CollectionHealth(BaseModel):
    reddit: Literal["ok", "stale", "empty"]
    prices: Literal["ok", "stale", "empty"]
    daily_features: Literal["ok", "stale", "empty"]
    jobs: Literal["ok", "warning"]

    model_config = ConfigDict(from_attributes=True)


class CollectionThresholds(BaseModel):
    reddit_stale_after_minutes: int
    prices_stale_after_days: int
    features_stale_after_days: int

    model_config = ConfigDict(from_attributes=True)


class CollectionStatusResponse(BaseModel):
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatus]
    reddit: RedditCollectionStatus
    prices: PriceCollectionStatus
    daily_features: DailyFeatureStatus
    health: CollectionHealth
    thresholds: CollectionThresholds

    model_config = ConfigDict(from_attributes=True)


class StaleSymbolStatus(BaseModel):
    symbol: str
    last_reddit_collected_at_utc: datetime | None = None
    last_price_date: datetime | None = None
    last_daily_feature_day: datetime | None = None
    stale_reasons: list[str]

    model_config = ConfigDict(from_attributes=True)


class JobRun(BaseModel):
    """Single job run record for history API."""

    id: int | None = None
    job_name: str
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    success: bool | None = None
    error_message: str | None = None
    duration_seconds: float | None = None

    model_config = ConfigDict(from_attributes=True)


def _convert_jobs(results: list[JobStatusResult]) -> list[JobStatus]:
    return [JobStatus.model_validate(r) for r in results]


def _convert_reddit(result: RedditCollectionStatusResult) -> RedditCollectionStatus:
    return RedditCollectionStatus.model_validate(result)


def _convert_prices(result: PriceCollectionStatusResult) -> PriceCollectionStatus:
    return PriceCollectionStatus.model_validate(result)


def _convert_daily_features(result: DailyFeatureStatusResult) -> DailyFeatureStatus:
    return DailyFeatureStatus.model_validate(result)


def _convert_health(result: HealthResult) -> CollectionHealth:
    return CollectionHealth.model_validate(result)


@router.get("/collection", response_model=CollectionStatusResponse)
def get_collection_status_api(db: Session = Depends(get_session)) -> CollectionStatusResponse:
    """Return current data collection / ingestion status."""
    try:
        status_result: CollectionStatusResult = get_collection_status(db)
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc

    return CollectionStatusResponse(
        server_time_utc=status_result.server_time_utc,
        market_time_local=status_result.market_time_local,
        jobs=_convert_jobs(status_result.jobs),
        reddit=_convert_reddit(status_result.reddit),
        prices=_convert_prices(status_result.prices),
        daily_features=_convert_daily_features(status_result.daily_features),
        health=_convert_health(status_result.health),
        thresholds=CollectionThresholds(
            reddit_stale_after_minutes=status_result.health.reddit_stale_after_minutes,
            prices_stale_after_days=status_result.health.prices_stale_after_days,
            features_stale_after_days=status_result.health.features_stale_after_days,
        ),
    )


def _as_utc_aware(dt: datetime | None) -> datetime | None:
    """Normalize datetime to UTC-aware; treat naive as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/jobs/runs", response_model=list[JobRun])
def get_job_runs_all(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_session),
) -> list[JobRun]:
    """Return recent job executions across all jobs, most recent first."""
    try:
        repo = JobExecutionRepository(db)
        runs = repo.list_recent_runs(job_name=None, limit=limit)
        return [_job_run_from_history(h) for h in runs]
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("UnexpectedError", str(exc)),
        ) from exc


@router.get("/jobs/{job_name}/runs", response_model=list[JobRun])
def get_job_runs_for_job(
    job_name: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[JobRun]:
    """Return recent job executions for a specific job, most recent first."""
    try:
        repo = JobExecutionRepository(db)
        runs = repo.list_recent_runs(job_name=job_name, limit=limit)
        return [_job_run_from_history(h) for h in runs]
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("UnexpectedError", str(exc)),
        ) from exc


def _job_run_from_history(h: JobRunHistory) -> JobRun:
    """Build JobRun from JobRunHistory, normalizing datetimes to UTC-aware."""
    finished = _as_utc_aware(h.run_at)
    started = _as_utc_aware(h.started_at)
    duration = h.duration_seconds
    return JobRun(
        id=h.id,
        job_name=h.job_name,
        started_at_utc=started,
        finished_at_utc=finished,
        success=h.success,
        error_message=h.error_message,
        duration_seconds=duration,
    )


@router.get("/symbols/stale", response_model=list[StaleSymbolStatus])
def get_stale_symbols_api(
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[StaleSymbolStatus]:
    """Return top-N stalest symbols across Reddit, prices, and daily features."""
    try:
        results: list[SymbolStalenessResult] = get_stale_symbols(db, limit)
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc

    return [StaleSymbolStatus.model_validate(r) for r in results]

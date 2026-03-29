from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.models.job_run_history import JobRunHistory
from backend.app.services.status_service import (
    CollectionStatusResult,
    HealthResult,
    JobStatusResult,
    PriceCollectionStatusResult,
    SymbolStalenessResult,
    get_collection_status,
    get_stale_symbols,
)
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import DataAccessError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])


class JobStatus(BaseModel):
    job_id: str
    schedule: str | None = None
    last_run_utc: datetime | None = None
    last_success_utc: datetime | None = None
    last_status: Literal["ran", "never"]
    last_error: str | None = None
    duration_seconds: float | None = None
    last_run_summary: str | None = None
    last_success_summary: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PriceCollectionStatus(BaseModel):
    newest_price_date: date | None = None
    price_rows_last_7d: int
    price_rows_last_30d: int

    model_config = ConfigDict(from_attributes=True)


class CollectionHealth(BaseModel):
    prices: Literal["ok", "stale", "empty"]
    jobs: Literal["ok", "warning"]

    model_config = ConfigDict(from_attributes=True)


class CollectionThresholds(BaseModel):
    prices_stale_after_days: int

    model_config = ConfigDict(from_attributes=True)


class CollectionStatusResponse(BaseModel):
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatus]
    prices: PriceCollectionStatus
    health: CollectionHealth
    thresholds: CollectionThresholds

    model_config = ConfigDict(from_attributes=True)


class StaleSymbolStatus(BaseModel):
    symbol: str
    last_price_date: date | None = None
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
    summary: str | None = None
    metrics: dict[str, object] | None = None

    model_config = ConfigDict(from_attributes=True)


def _convert_jobs(results: list[JobStatusResult]) -> list[JobStatus]:
    return [JobStatus.model_validate(r) for r in results]


def _convert_prices(result: PriceCollectionStatusResult) -> PriceCollectionStatus:
    return PriceCollectionStatus.model_validate(result)


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
        prices=_convert_prices(status_result.prices),
        health=_convert_health(status_result.health),
        thresholds=CollectionThresholds(
            prices_stale_after_days=status_result.health.prices_stale_after_days,
        ),
    )


def _as_utc_aware(dt: datetime | None) -> datetime | None:
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


def _parse_metrics_json(metrics_json: str | None) -> dict[str, object] | None:
    if not metrics_json:
        return None
    try:
        return json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.debug("Failed to parse job run metrics_json: %s", exc)
        return None


def _job_run_from_history(h: JobRunHistory) -> JobRun:
    finished = _as_utc_aware(h.run_at)
    started = _as_utc_aware(h.started_at)
    duration = h.duration_seconds
    metrics = _parse_metrics_json(getattr(h, "metrics_json", None))
    return JobRun(
        id=h.id,
        job_name=h.job_name,
        started_at_utc=started,
        finished_at_utc=finished,
        success=h.success,
        error_message=h.error_message,
        duration_seconds=duration,
        summary=getattr(h, "summary", None),
        metrics=metrics,
    )


@router.get("/symbols/stale", response_model=list[StaleSymbolStatus])
def get_stale_symbols_api(
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[StaleSymbolStatus]:
    """Return top-N stalest symbols by price freshness."""
    try:
        results: list[SymbolStalenessResult] = get_stale_symbols(db, limit)
    except DataAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("DataAccessError", str(exc)),
        ) from exc

    return [StaleSymbolStatus.model_validate(r) for r in results]

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.services.status_service import (
    CollectionStatusResult,
    DailyFeatureStatusResult,
    JobStatusResult,
    PriceCollectionStatusResult,
    RedditCollectionStatusResult,
    get_collection_status,
)
from backend.app.utils.api_errors import error_detail
from backend.app.utils.errors import DataAccessError


router = APIRouter(prefix="/api/status", tags=["status"])


class JobStatus(BaseModel):
    job_id: str
    schedule: str | None = None
    last_start_utc: datetime | None = None
    last_end_utc: datetime | None = None
    last_success_utc: datetime | None = None
    last_status: Literal["success", "failure", "running", "never"]
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


class CollectionStatusResponse(BaseModel):
    server_time_utc: datetime
    market_time_local: datetime
    jobs: list[JobStatus]
    reddit: RedditCollectionStatus
    prices: PriceCollectionStatus
    daily_features: DailyFeatureStatus

    model_config = ConfigDict(from_attributes=True)


def _convert_jobs(results: list[JobStatusResult]) -> list[JobStatus]:
    return [JobStatus.model_validate(r) for r in results]


def _convert_reddit(result: RedditCollectionStatusResult) -> RedditCollectionStatus:
    return RedditCollectionStatus.model_validate(result)


def _convert_prices(result: PriceCollectionStatusResult) -> PriceCollectionStatus:
    return PriceCollectionStatus.model_validate(result)


def _convert_daily_features(result: DailyFeatureStatusResult) -> DailyFeatureStatus:
    return DailyFeatureStatus.model_validate(result)


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
    )


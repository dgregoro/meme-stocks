from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.utils.api_errors import error_detail
from backend.app.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# Store scheduler instance (set by main.py on startup)
_scheduler_instance: SchedulerService | None = None


def set_scheduler(scheduler: SchedulerService | None) -> None:
    """Set the scheduler instance for manual job execution."""
    global _scheduler_instance
    _scheduler_instance = scheduler


def get_scheduler() -> SchedulerService:
    """Get the scheduler instance, raising an error if not available."""
    if _scheduler_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("ServiceUnavailable", "Scheduler not initialized"),
        )
    return _scheduler_instance


class JobResponse(BaseModel):
    """Response model for job execution."""

    job_name: str
    status: str
    message: str
    stats: dict[str, int] | None = None


@router.post("/price-collection", response_model=JobResponse)
def trigger_price_collection(
    db: Session = Depends(get_session),
    scheduler: SchedulerService = Depends(get_scheduler),
) -> JobResponse:
    """Manually trigger price data collection.

    This endpoint runs the price collection job immediately for all tracked stocks.
    """
    try:
        stats = scheduler._collect_price_data(db)
        job_repo = JobExecutionRepository(db)
        rows_inserted = stats.get("rows_inserted", 0)
        symbols = stats.get("symbols", 0)
        summary = f"prices: {rows_inserted} rows inserted for {symbols} symbols"
        job_repo.record_run(
            "price_collection",
            summary=summary,
            metrics=stats,
        )
        db.commit()

        return JobResponse(
            job_name="price_collection",
            status="success",
            message="Price collection completed successfully",
        )
    except Exception as exc:
        logger.error(f"Error in manual price collection: {exc}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Price collection failed: {exc}"),
        ) from exc


@router.post("/notification-check", response_model=JobResponse)
def trigger_notification_check(
    db: Session = Depends(get_session),
    scheduler: SchedulerService = Depends(get_scheduler),
) -> JobResponse:
    """Manually trigger notification check for all stocks.

    This endpoint runs the notification check job immediately, generating
    alerts for any unusual activity detected.
    """
    try:
        stats = scheduler._check_notifications(db)
        job_repo = JobExecutionRepository(db)
        notifs = stats.get("notifications_generated", 0)
        symbols = stats.get("symbols_checked", 0)
        summary = f"notifications: {notifs} generated for {symbols} symbols"
        job_repo.record_run(
            "notification_check",
            summary=summary,
            metrics=stats,
        )
        db.commit()

        return JobResponse(
            job_name="notification_check",
            status="success",
            message="Notification check completed successfully",
        )
    except Exception as exc:
        logger.error(f"Error in manual notification check: {exc}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Notification check failed: {exc}"),
        ) from exc


@router.post("/leader-follower-detection", response_model=JobResponse)
def trigger_leader_follower_detection(
    db: Session = Depends(get_session),
    scheduler: SchedulerService = Depends(get_scheduler),
) -> JobResponse:
    """Manually trigger leader-follower signal detection.

    Runs the detection job immediately, regardless of the scheduled time.
    Useful for testing or on-demand runs when leader_follower_enabled is set.
    """
    try:
        scheduler._leader_follower_detection_job()
        job_repo = JobExecutionRepository(db)
        runs = job_repo.list_recent_runs("leader_follower_detection", limit=1)
        if runs:
            r = runs[0]
            return JobResponse(
                job_name="leader_follower_detection",
                status="success",
                message="Leader-follower detection completed successfully",
                stats={"run_id": r.id},
            )
        return JobResponse(
            job_name="leader_follower_detection",
            status="success",
            message="Leader-follower detection completed",
            stats=None,
        )
    except Exception as exc:
        logger.error("Error in manual leader-follower detection: %s", exc, exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail(
                "InternalServerError",
                f"Leader-follower detection failed: {exc}",
            ),
        ) from exc


# Map URL path segment (hyphenated) to internal job name (underscore)
JOB_NAME_FROM_PATH: dict[str, str] = {
    "price-collection": "price_collection",
    "daily-analysis": "daily_analysis",
    "notification-check": "notification_check",
    "leader-follower-detection": "leader_follower_detection",
}


class JobRunResponse(BaseModel):
    """Response model for a single job run."""

    id: int
    job_name: str
    run_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/{job_name}/runs", response_model=List[JobRunResponse])
def get_job_runs(
    job_name: str,
    db: Session = Depends(get_session),
) -> List[JobRunResponse]:
    """Get the last 30 runs for a job.

    Valid job_name values: price-collection, daily-analysis, notification-check,
    leader-follower-detection
    """
    internal_name = JOB_NAME_FROM_PATH.get(job_name)
    if internal_name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("NotFound", f"Unknown job: {job_name}"),
        )
    repo = JobExecutionRepository(db)
    runs = repo.list_recent_runs(internal_name, limit=30)
    return [
        JobRunResponse(
            id=r.id,
            job_name=r.job_name,
            run_at=r.run_at.isoformat(),
        )
        for r in runs
    ]

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.services.job_metrics import (
    REDDIT_POSTS_FETCHED,
    REDDIT_POSTS_INSERTED,
    REDDIT_STOCKS_CREATED,
    REDDIT_SYMBOLS_MENTIONED,
)
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


@router.post("/reddit-collection", response_model=JobResponse)
def trigger_reddit_collection(
    db: Session = Depends(get_session),
    scheduler: SchedulerService = Depends(get_scheduler),
) -> JobResponse:
    """Manually trigger Reddit data collection.

    This endpoint runs the Reddit collection job immediately, regardless of
    the scheduled interval. Useful for testing or on-demand data updates.
    """
    try:
        stats = scheduler._collect_reddit_data(db)
        job_repo = JobExecutionRepository(db)
        posts_inserted = stats.get(REDDIT_POSTS_INSERTED, 0)
        posts_fetched = stats.get(REDDIT_POSTS_FETCHED, 0)
        symbols_mentioned = stats.get(REDDIT_SYMBOLS_MENTIONED, 0)
        summary = f"reddit: inserted {posts_inserted} posts ({posts_fetched} fetched), symbols={symbols_mentioned}"
        metrics = {
            REDDIT_POSTS_FETCHED: posts_fetched,
            REDDIT_POSTS_INSERTED: posts_inserted,
            REDDIT_SYMBOLS_MENTIONED: symbols_mentioned,
            REDDIT_STOCKS_CREATED: stats.get(REDDIT_STOCKS_CREATED, 0),
        }
        job_repo.record_run(
            "reddit_collection",
            summary=summary,
            metrics=metrics,
        )
        db.commit()

        return JobResponse(
            job_name="reddit_collection",
            status="success",
            message="Reddit collection completed successfully",
            stats=stats,
        )
    except Exception as exc:
        logger.error(f"Error in manual Reddit collection: {exc}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Reddit collection failed: {exc}"),
        ) from exc


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


# Map URL path segment (hyphenated) to internal job name (underscore)
JOB_NAME_FROM_PATH: dict[str, str] = {
    "reddit-collection": "reddit_collection",
    "price-collection": "price_collection",
    "daily-analysis": "daily_analysis",
    "notification-check": "notification_check",
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

    Valid job_name values: reddit-collection, price-collection, daily-analysis, notification-check
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


class RedditPostResponse(BaseModel):
    """Response model for Reddit post."""

    id: str
    stock_symbol: str
    subreddit: str
    title: str
    author: str
    upvotes: int
    comments: int
    url: str
    posted_at: str
    collected_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/reddit-collection/recent", response_model=List[RedditPostResponse])
def get_recent_reddit_posts(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
) -> List[RedditPostResponse]:
    """Get recently collected Reddit posts.

    Args:
        limit: Maximum number of posts to return (default: 20, max: 100)
    """
    try:
        from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
        from backend.app.data.repositories.reddit_symbol_mention_repo import (
            RedditSymbolMentionRepository,
        )

        reddit_repo = RedditPostRepository(db)
        mention_repo = RedditSymbolMentionRepository(db)

        posts = reddit_repo.list_recent(limit=limit)

        result = []
        for post in posts:
            # Get symbols mentioned in this post
            symbols = mention_repo.get_symbols_for_post(post.id)
            # For backward compatibility, use first symbol or empty string
            primary_symbol = symbols[0] if symbols else ""

            result.append(
                RedditPostResponse(
                    id=post.id,
                    stock_symbol=primary_symbol,
                    subreddit=post.subreddit,
                    title=post.title,
                    author=post.author,
                    upvotes=post.upvotes,
                    comments=post.comments,
                    url=post.url,
                    posted_at=post.posted_at.isoformat(),
                    collected_at=post.collected_at.isoformat(),
                )
            )

        return result
    except Exception as exc:
        logger.error(f"Error fetching recent Reddit posts: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("InternalServerError", f"Failed to fetch recent Reddit posts: {exc}"),
        ) from exc

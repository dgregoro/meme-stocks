from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# Store scheduler instance (set by main.py on startup)
_scheduler_instance: SchedulerService | None = None


def set_scheduler(scheduler: SchedulerService) -> None:
    """Set the scheduler instance for manual job execution."""
    global _scheduler_instance
    _scheduler_instance = scheduler


def get_scheduler() -> SchedulerService:
    """Get the scheduler instance, raising an error if not available."""
    if _scheduler_instance is None:
        raise HTTPException(
            status_code=503, detail="Scheduler not initialized"
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
        job_repo.record_run("reddit_collection")
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
            status_code=500,
            detail=f"Reddit collection failed: {str(exc)}",
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
        scheduler._collect_price_data(db)
        job_repo = JobExecutionRepository(db)
        job_repo.record_run("price_collection")
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
            status_code=500,
            detail=f"Price collection failed: {str(exc)}",
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
        scheduler._check_notifications(db)
        job_repo = JobExecutionRepository(db)
        job_repo.record_run("notification_check")
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
            status_code=500,
            detail=f"Notification check failed: {str(exc)}",
        ) from exc


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

    class Config:
        from_attributes = True


@router.get("/reddit-collection/recent", response_model=List[RedditPostResponse])
def get_recent_reddit_posts(
    limit: int = 20,
    db: Session = Depends(get_session),
) -> List[RedditPostResponse]:
    """Get recently collected Reddit posts.
    
    Args:
        limit: Maximum number of posts to return (default: 20, max: 100)
    """
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    reddit_repo = RedditPostRepository(db)
    # Get posts from all stocks, ordered by collection time
    from sqlalchemy import select
    from backend.app.models.reddit_post import RedditPost
    
    stmt = (
        select(RedditPost)
        .order_by(RedditPost.collected_at.desc())
        .limit(limit)
    )
    
    posts = list(db.execute(stmt).scalars().all())
    
    return [
        RedditPostResponse(
            id=post.id,
            stock_symbol=post.stock_symbol,
            subreddit=post.subreddit,
            title=post.title,
            author=post.author,
            upvotes=post.upvotes,
            comments=post.comments,
            url=post.url,
            posted_at=post.posted_at.isoformat(),
            collected_at=post.collected_at.isoformat(),
        )
        for post in posts
    ]


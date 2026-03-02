from __future__ import annotations

from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import get_session
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_daily_feature_repo import RedditDailyFeatureRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.utils.stock_helpers import require_stock
from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    calculate_weighted_sentiment,
    classify_sentiment,
)


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class RedditMentionResponse(BaseModel):
    """Single Reddit mention with source (subreddit, url) for display in web/CLI."""

    id: str
    subreddit: str
    title: str
    url: str
    author: str
    upvotes: int
    comments: int
    posted_at: str
    collected_at: str

    model_config = ConfigDict(from_attributes=True)


class SentimentResponse(BaseModel):
    stock_symbol: str
    score: float | None
    mention_count: int
    window_hours: int
    classification: str


class PricePointResponse(BaseModel):
    date: str  # ISO date
    open: float
    high: float
    low: float
    close: float
    volume: int

    model_config = ConfigDict(from_attributes=True)


class RedditDailyFeaturePointResponse(BaseModel):
    trading_day: str
    mention_count: int
    unique_authors: int
    total_upvotes: int
    total_comments: int
    upvote_weighted_mentions: float


@router.get("/{symbol}/sentiment", response_model=SentimentResponse)
def get_stock_sentiment(symbol: str, db: Session = Depends(get_session)) -> SentimentResponse:
    """Get aggregated sentiment from Reddit mentions for a stock (24h window)."""
    require_stock(db, symbol)

    reddit_repo = RedditPostRepository(db)
    posts = reddit_repo.list_for_stock(symbol)

    window = timedelta(hours=get_settings().sentiment_window_hours)
    summary: SentimentSummary = calculate_weighted_sentiment(symbol, posts, window=window)
    classification = classify_sentiment(summary.score)

    return SentimentResponse(
        stock_symbol=symbol,
        score=summary.score,
        mention_count=summary.mention_count,
        window_hours=int(summary.window.total_seconds() // 3600),
        classification=classification,
    )


@router.get("/{symbol}/mentions", response_model=List[RedditMentionResponse])
def get_stock_mentions(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
) -> List[RedditMentionResponse]:
    """Get recent Reddit mentions for a stock, with source (subreddit, url) for web/CLI."""
    require_stock(db, symbol)

    reddit_repo = RedditPostRepository(db)
    posts = reddit_repo.list_for_stock(symbol)

    result = []
    for post in posts[:limit]:
        result.append(
            RedditMentionResponse(
                id=post.id,
                subreddit=post.subreddit,
                title=post.title,
                url=post.url,
                author=post.author,
                upvotes=post.upvotes,
                comments=post.comments,
                posted_at=post.posted_at.isoformat(),
                collected_at=post.collected_at.isoformat(),
            )
        )
    return result


@router.get("/{symbol}/prices", response_model=List[PricePointResponse])
def get_stock_prices(symbol: str, db: Session = Depends(get_session)) -> List[PricePointResponse]:
    """Get OHLCV price history for a stock. Returns 404 if stock not found."""
    require_stock(db, symbol)

    price_repo = PriceDataRepository(db)
    prices = price_repo.list_for_stock(symbol)
    return [
        PricePointResponse(
            date=p.date.isoformat(),
            open=p.open,
            high=p.high,
            low=p.low,
            close=p.close,
            volume=p.volume,
        )
        for p in prices
    ]


@router.get(
    "/{symbol}/reddit-daily-features",
    response_model=List[RedditDailyFeaturePointResponse],
)
def get_reddit_daily_features(
    symbol: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: Session = Depends(get_session),
) -> List[RedditDailyFeaturePointResponse]:
    """Get persisted daily Reddit aggregates for a stock over a date range."""
    require_stock(db, symbol)

    settings = get_settings()
    repo = RedditDailyFeatureRepository(db)

    # Default range: last reddit_daily_features_lookback_days up to today (market timezone).
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt

    tz = ZoneInfo(settings.market_timezone)
    end_day = end or _dt.now(tz).date()
    start_day = start or (end_day - timedelta(days=settings.reddit_daily_features_lookback_days))

    if start_day > end_day:
        start_day, end_day = end_day, start_day

    rows = repo.list_for_symbol(symbol, start_day, end_day)
    return [
        RedditDailyFeaturePointResponse(
            trading_day=row.trading_day.isoformat(),
            mention_count=row.mention_count,
            unique_authors=row.unique_authors,
            total_upvotes=row.total_upvotes,
            total_comments=row.total_comments,
            upvote_weighted_mentions=row.upvote_weighted_mentions,
        )
        for row in rows
    ]

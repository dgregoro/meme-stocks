from __future__ import annotations

from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.database import get_session
from backend.app.data.repositories.price_data_repo import PriceDataRepository
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

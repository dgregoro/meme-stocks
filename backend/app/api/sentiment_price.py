from __future__ import annotations

from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.data.database import get_session
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    calculate_weighted_sentiment,
    classify_sentiment,
)


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


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
    # Ensure stock exists; keep behavior explicit.
    if StockRepository(db).get(symbol) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_type": "NotFoundError",
                "message": "Stock not found",
            },
        )

    reddit_repo = RedditPostRepository(db)
    posts = reddit_repo.list_for_stock(symbol)

    # Use a fixed 24h window for now; this can be made configurable later.
    summary: SentimentSummary = calculate_weighted_sentiment(symbol, posts, window=timedelta(hours=24))
    classification = classify_sentiment(summary.score)

    return SentimentResponse(
        stock_symbol=symbol,
        score=summary.score,
        mention_count=summary.mention_count,
        window_hours=int(summary.window.total_seconds() // 3600),
        classification=classification,
    )


@router.get("/{symbol}/prices", response_model=List[PricePointResponse])
def get_stock_prices(symbol: str, db: Session = Depends(get_session)) -> List[PricePointResponse]:
    """Get OHLCV price history for a stock. Returns 404 if stock not found."""
    if StockRepository(db).get(symbol) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_type": "NotFoundError",
                "message": "Stock not found",
            },
        )

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

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.services.pattern_analyzer import PriceTrend, analyze_price_trend
from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    calculate_weighted_sentiment,
)
from backend.app.services.yahoo_service import PriceBar


@dataclass(frozen=True)
class StockAnalysisRow:
    symbol: str
    sentiment_score: float | None
    mention_count: int
    price_trend: str
    composite_score: float


def build_price_bars_for_stock(
    symbol: str, repo: PriceDataRepository
) -> List[PriceBar]:
    prices = repo.list_for_stock(symbol)
    bars: list[PriceBar] = []
    for p in prices:
        bars.append(
            PriceBar(
                stock_symbol=symbol,
                date=p.date,
                open=p.open,
                high=p.high,
                low=p.low,
                close=p.close,
                volume=p.volume,
                source_timestamp=datetime.now(timezone.utc),
            )
        )
    return bars


def compute_composite_score(
    sentiment: SentimentSummary, trend: PriceTrend
) -> float:
    """Combine sentiment and trend into a simple composite score [0, 1].

    This is intentionally simple and transparent:
    - sentiment in [-1, 1] is shifted to [0, 1]
    - trend contributes a fixed amount based on direction
    """

    # Sentiment contribution: map [-1, 1] -> [0, 1]
    if sentiment.score is None:
        sentiment_component = 0.5
    else:
        sentiment_component = (sentiment.score + 1.0) / 2.0

    # Trend contribution: uptrend > sideways > downtrend
    if trend.direction == "uptrend":
        trend_component = 1.0
    elif trend.direction == "downtrend":
        trend_component = 0.0
    else:
        trend_component = 0.5

    # Simple weighted average
    return round(sentiment_component * 0.6 + trend_component * 0.4, 4)


def run_daily_analysis(
    db: Session, *, window: timedelta = timedelta(hours=24)
) -> List[StockAnalysisRow]:
    """Produce a ranked list of stocks with sentiment and trend.

    This function uses existing repositories and analysis helpers and does
    not perform any persistence itself.
    """

    stock_repo = StockRepository(db)
    reddit_repo = RedditPostRepository(db)
    price_repo = PriceDataRepository(db)

    now = datetime.now(timezone.utc)
    stocks = stock_repo.list()

    rows: list[StockAnalysisRow] = []

    for stock in stocks:
        posts = reddit_repo.list_for_stock(stock.symbol)
        sentiment = calculate_weighted_sentiment(
            stock.symbol, posts, window=window, now=now
        )

        bars = build_price_bars_for_stock(stock.symbol, price_repo)
        trend = analyze_price_trend(bars)

        composite = compute_composite_score(sentiment, trend)
        rows.append(
            StockAnalysisRow(
                symbol=stock.symbol,
                sentiment_score=sentiment.score,
                mention_count=sentiment.mention_count,
                price_trend=trend.direction,
                composite_score=composite,
            )
        )

    # Sort by composite_score descending
    rows.sort(key=lambda r: r.composite_score, reverse=True)
    return rows



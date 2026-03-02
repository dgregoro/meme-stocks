"""Daily aggregated Reddit features per (symbol, trading_day) for causal research."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class RedditDailyFeature(Base):
    """Daily Reddit activity aggregates per symbol and trading day.

    Keyed by posted_at with after-hours rule: posts at or after market close
    count toward the next trading day. Used for leakage-safe causal/predictive research.
    """

    __tablename__ = "reddit_daily_features"
    __table_args__ = (Index("idx_reddit_daily_features_trading_day", "trading_day"),)

    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol", ondelete="CASCADE"), primary_key=True, index=True
    )
    trading_day: Mapped[dt.date] = mapped_column(Date, primary_key=True, index=True)

    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_authors: Mapped[int] = mapped_column(Integer, nullable=False)
    total_upvotes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_comments: Mapped[int] = mapped_column(Integer, nullable=False)
    upvote_weighted_mentions: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    stock = relationship("Stock", back_populates="reddit_daily_features")

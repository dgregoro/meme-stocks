from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class Stock(Base):
    """A tracked stock symbol with metadata (name, sector, market cap).

    Stocks must exist before paper trades or Reddit symbol mentions can reference them.
    """

    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    reddit_mentions = relationship("RedditSymbolMention", back_populates="stock")

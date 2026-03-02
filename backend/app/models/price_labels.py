from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class PriceLabel(Base):
    """Forward-return label for a stock over a given horizon in calendar days.

    Each row represents the forward return from close[D] to close[D + horizon_days]:
        fwd_return = close[D + horizon_days] / close[D] - 1

    Labels are only defined when both closes exist in PriceData.
    """

    __tablename__ = "price_labels"
    __table_args__ = (Index("idx_price_labels_trading_day", "trading_day"),)

    symbol: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("stocks.symbol", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    trading_day: Mapped[dt.date] = mapped_column(Date, primary_key=True, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)

    fwd_return: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    stock = relationship("Stock")

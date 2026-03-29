"""Persisted extreme daily return events for mean-reversion research (016)."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class ExtremeMoveEvent(Base):
    """Single-symbol day where close-to-close return exceeds configured thresholds."""

    __tablename__ = "extreme_move_events"
    __table_args__ = (UniqueConstraint("symbol", "event_date", name="uq_extreme_move_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)
    return_pct: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    magnitude_bucket: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_bucket: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(timezone.utc)
    )

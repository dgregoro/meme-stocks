"""Persisted volume spike vs rolling baseline events (research, 015)."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class VolumeSpikeEvent(Base):
    """Single-symbol daily bar where volume exceeds rolling baseline by configured ratio."""

    __tablename__ = "volume_spike_events"
    __table_args__ = (UniqueConstraint("symbol", "event_date", name="uq_volume_spike_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)
    volume: Mapped[int] = mapped_column(Integer)
    baseline_volume: Mapped[float] = mapped_column(Float)
    volume_ratio: Mapped[float] = mapped_column(Float)
    same_day_return_pct: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(timezone.utc)
    )

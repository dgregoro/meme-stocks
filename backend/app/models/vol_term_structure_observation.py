"""Persisted VIX and VIX3M closes for S3 volatility term-structure research (021)."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from sqlalchemy import Date, DateTime, Float, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class VolTermStructureObservation(Base):
    """One calendar/trading row: spot vs medium-term implied vol for regime labeling."""

    __tablename__ = "vol_term_structure_observations"
    __table_args__ = (UniqueConstraint("observation_date", name="uq_vol_term_observation_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[dt.date] = mapped_column(Date, index=True)
    vix_close: Mapped[float] = mapped_column(Float)
    vix3m_close: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(timezone.utc)
    )

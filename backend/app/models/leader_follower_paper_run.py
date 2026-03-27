"""Persisted leader-follower paper trading simulation run."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerPaperRun(Base):
    """One paper-trading simulation over a date range with a frozen config."""

    __tablename__ = "leader_follower_paper_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    cumulative_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False)

    trades = relationship(
        "LeaderFollowerPaperTrade",
        back_populates="run",
        cascade="all, delete-orphan",
    )

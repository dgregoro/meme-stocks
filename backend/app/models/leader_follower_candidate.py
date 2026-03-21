"""LeaderFollowerCandidate model for follower candidates produced during detection."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class LeaderFollowerCandidate(Base):
    """Records a follower candidate produced by select_follower_candidates during a run."""

    __tablename__ = "leader_follower_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_run_history.id"), nullable=False, index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    leader_symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), nullable=False, index=True)
    follower_symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), nullable=False, index=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

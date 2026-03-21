"""LeaderEvent model for detected significant price/volume moves."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class LeaderEvent(Base):
    """Records a detected significant move (leader) at a given date."""

    __tablename__ = "leader_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    leader_symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), index=True, nullable=False)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    volume_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # 'up' | 'down'
    job_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("job_run_history.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

"""LeaderFollowerSignal model for follower opportunity signals."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Date, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class LeaderFollowerSignal(Base):
    """A follower opportunity signal linking leader and follower with strength and metrics."""

    __tablename__ = "leader_follower_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    leader_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol"), index=True, nullable=False
    )
    follower_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol"), index=True, nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    signal_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    strength_score: Mapped[float] = mapped_column(Float, nullable=False)
    leader_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    leader_volume_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

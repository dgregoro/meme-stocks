"""Persisted walk-forward optimization run (research tooling)."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerOptimizationRun(Base):
    """One grid search over train/validate/(optional) test windows."""

    __tablename__ = "leader_follower_optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    train_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    train_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    validate_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    validate_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    test_start: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    test_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    ranking_method: Mapped[str] = mapped_column(String(64), nullable=False)

    results = relationship(
        "LeaderFollowerOptimizationResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )

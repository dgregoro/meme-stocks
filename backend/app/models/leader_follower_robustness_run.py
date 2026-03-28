"""Persisted rolling robustness evaluation run (research tooling)."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerRobustnessRun(Base):
    """One rolling walk-forward robustness run over many splits."""

    __tablename__ = "leader_follower_robustness_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    overall_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    overall_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    train_window_spec: Mapped[str] = mapped_column(Text, nullable=False)
    validate_window_spec: Mapped[str] = mapped_column(Text, nullable=False)
    test_window_spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_spec: Mapped[str] = mapped_column(Text, nullable=False)
    split_count: Mapped[int] = mapped_column(Integer, nullable=False)
    grid_config_json: Mapped[str] = mapped_column(Text, nullable=False)
    ranking_method: Mapped[str] = mapped_column(String(64), nullable=False)

    split_results = relationship(
        "LeaderFollowerRobustnessSplitResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    aggregates = relationship(
        "LeaderFollowerRobustnessAggregate",
        back_populates="run",
        cascade="all, delete-orphan",
    )

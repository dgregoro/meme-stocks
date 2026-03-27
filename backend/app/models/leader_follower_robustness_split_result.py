"""Per-split, per-candidate metrics for a robustness run."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerRobustnessSplitResult(Base):
    __tablename__ = "leader_follower_robustness_split_results"
    __table_args__ = (Index("ix_lf_robust_split_run_split_idx", "run_id", "split_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leader_follower_robustness_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    split_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    train_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    train_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    validate_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    validate_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    test_start: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    test_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    train_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    validate_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    test_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("LeaderFollowerRobustnessRun", back_populates="split_results")

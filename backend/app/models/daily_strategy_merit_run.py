"""Persisted daily-strategy merit / bundle evaluation runs (S1/S2 research)."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class DailyStrategyMeritRun(Base):
    """One row per ``s1-merit`` / ``s2-merit`` / ``eval-bundle`` JSON payload."""

    __tablename__ = "daily_strategy_merit_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(timezone.utc),
        index=True,
    )
    report_kind: Mapped[str] = mapped_column(String(64), index=True)
    strategy_id: Mapped[str] = mapped_column(String(8), index=True)
    eval_start: Mapped[dt.date] = mapped_column(Date, index=True)
    eval_end: Mapped[dt.date] = mapped_column(Date, index=True)
    n_splits: Mapped[int] = mapped_column(Integer, default=1)
    split_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    symbols_json: Mapped[str] = mapped_column(Text)
    report_json: Mapped[str] = mapped_column(Text)
    checklist_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rolling_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    all_gates_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

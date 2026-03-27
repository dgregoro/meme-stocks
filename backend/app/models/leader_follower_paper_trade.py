"""Single simulated trade from a leader-follower paper run."""

from __future__ import annotations

import datetime as dt
from datetime import datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class LeaderFollowerPaperTrade(Base):
    """Simulated trade for one signal with entry/exit from price data."""

    __tablename__ = "leader_follower_paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leader_follower_paper_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    leader_symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    follower_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    signal_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    signal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leader_follower_signals.id", ondelete="SET NULL"), nullable=True
    )
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    holding_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    net_return_pct: Mapped[float] = mapped_column(Float, nullable=False)

    run = relationship("LeaderFollowerPaperRun", back_populates="trades")

"""Single simulated trade from a leader-follower paper run."""

from __future__ import annotations

import datetime as dt
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
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
    sector_etf_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sector_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_ma: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_rolling_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_confirmation_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime_benchmark_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    regime_decision_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    regime_benchmark_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime_benchmark_ma: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime_market_uptrend_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime_low_volatility_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime_sector_strength_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime_filter_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    run = relationship("LeaderFollowerPaperRun", back_populates="trades")

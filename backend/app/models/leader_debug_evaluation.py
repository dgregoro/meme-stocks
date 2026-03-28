"""LeaderDebugEvaluation model for symbol-level leader detection debug data."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class LeaderDebugEvaluation(Base):
    """Records per-symbol evaluation during leader detection for debugging."""

    __tablename__ = "leader_debug_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_run_history.id"), nullable=False, index=True)
    stock_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualified_as_leader: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reasons: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

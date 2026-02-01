from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class JobExecution(Base):
    """Tracks when scheduled jobs last ran for catch-up logic."""

    __tablename__ = "job_executions"

    job_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("idx_job_executions_last_run", "last_run_at"),)

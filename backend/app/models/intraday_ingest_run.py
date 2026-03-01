"""ORM model for intraday ingestion run summaries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class IntradayIngestRun(Base):
    """Records each intraday ingestion run for progress and audit."""

    __tablename__ = "intraday_ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    symbols_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bars_written: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

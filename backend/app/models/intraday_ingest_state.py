"""ORM model for per-symbol intraday ingestion state."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class IntradayIngestState(Base):
    """Tracks last ingested timestamp and status per symbol for incremental bars."""

    __tablename__ = "intraday_ingest_state"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_intraday_ingest_state_status", "status"),
        Index("idx_intraday_ingest_state_updated_at", "updated_at"),
    )

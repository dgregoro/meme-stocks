from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class SymbolUniverse(Base):
    """Model for storing a universe of valid stock symbols."""

    __tablename__ = "symbol_universe"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_etf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_symbol_universe_exchange", "exchange"),
        Index("idx_symbol_universe_last_seen", "last_seen"),
        Index("idx_symbol_universe_active", "is_active"),
    )


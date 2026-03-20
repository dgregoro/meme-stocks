"""StockGroup model for leader-follower group membership."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class StockGroup(Base):
    """Stock-to-group membership. One symbol may appear in multiple groups."""

    __tablename__ = "stock_groups"
    __table_args__ = (UniqueConstraint("group_id", "stock_symbol", name="uq_stock_groups_group_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stock_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

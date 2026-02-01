from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class Notification(Base):
    """User-facing alert for unusual activity (volume spike, price move, sentiment shift).

    Severity is 'low', 'medium', or 'high'. read indicates whether the user has seen it.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), index=True)
    type: Mapped[str] = mapped_column(String(64))  # e.g. 'volume_spike'
    message: Mapped[str] = mapped_column(String(512))
    severity: Mapped[str] = mapped_column(String(16))  # 'low' | 'medium' | 'high'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read: Mapped[bool] = mapped_column(Boolean, default=False)

from __future__ import annotations

import datetime as dt
from datetime import timezone

from sqlalchemy import String, Integer, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class PriceData(Base):
    __tablename__ = "price_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol"), index=True
    )

    date: Mapped[dt.date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)

    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(timezone.utc)
    )

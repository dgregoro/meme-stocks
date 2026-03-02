from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.price_data import PriceData
from backend.app.utils.errors import DataAccessError


class PriceDataRepository:
    """Data access for PriceData (OHLCV bars)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, price: PriceData) -> None:
        """Persist price data. Caller must commit the session."""
        try:
            self._session.add(price)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add price data") from exc

    def list_for_stock(self, symbol: str) -> Sequence[PriceData]:
        stmt = select(PriceData).where(PriceData.stock_symbol == symbol).order_by(PriceData.date.asc())
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list price data") from exc

    def get_for_date(self, symbol: str, on_date: date) -> PriceData | None:
        """Fetch OHLCV for a stock on a specific date, or None if missing."""
        stmt = select(PriceData).where(
            PriceData.stock_symbol == symbol,
            PriceData.date == on_date,
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to fetch price data for date") from exc

    def list_in_date_range(self, start_date: date, end_date: date) -> Sequence[PriceData]:
        """List all price data rows where date is in [start_date, end_date], ordered by symbol, date."""
        stmt = (
            select(PriceData)
            .where(
                PriceData.date >= start_date,
                PriceData.date <= end_date,
            )
            .order_by(PriceData.stock_symbol, PriceData.date)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list price data in date range") from exc

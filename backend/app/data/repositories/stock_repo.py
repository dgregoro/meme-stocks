from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.stock import Stock
from backend.app.utils.errors import DataAccessError


class StockRepository:
    """Repository for CRUD operations on Stock entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, symbol: str) -> Stock | None:
        stmt = select(Stock).where(Stock.symbol == symbol)
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except (
            SQLAlchemyError
        ) as exc:  # pragma: no cover - exercised via higher-level tests
            raise DataAccessError("Failed to fetch stock") from exc

    def list(self) -> Sequence[Stock]:
        stmt = select(Stock).order_by(Stock.symbol)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list stocks") from exc

    def add(self, stock: Stock) -> None:
        try:
            self._session.add(stock)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add stock") from exc

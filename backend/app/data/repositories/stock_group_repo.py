"""Repository for StockGroup (stock-to-group membership)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.stock_group import StockGroup
from backend.app.utils.errors import DataAccessError


class StockGroupRepository:
    """Data access for StockGroup entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_groups_for_symbol(self, symbol: str) -> list[str]:
        """Return group_ids for a symbol, ordered lexicographically."""
        stmt = select(StockGroup.group_id).where(StockGroup.stock_symbol == symbol).order_by(StockGroup.group_id)
        try:
            rows = self._session.execute(stmt).scalars().all()
            return [r for r in rows]
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get groups for symbol") from exc

    def get_all_symbol_group_pairs(self) -> list[tuple[str, str]]:
        """Return all (stock_symbol, group_id) pairs, ordered by symbol, group_id."""
        stmt = select(StockGroup.stock_symbol, StockGroup.group_id).order_by(
            StockGroup.stock_symbol, StockGroup.group_id
        )
        try:
            return list(self._session.execute(stmt).all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get symbol-group pairs") from exc

    def get_symbols_in_group(self, group_id: str) -> list[str]:
        """Return stock symbols in a group."""
        stmt = select(StockGroup.stock_symbol).where(StockGroup.group_id == group_id).order_by(StockGroup.stock_symbol)
        try:
            rows = self._session.execute(stmt).scalars().all()
            return [r for r in rows]
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get symbols in group") from exc

    def add(self, stock_group: StockGroup) -> None:
        """Persist a StockGroup. Caller must commit the session."""
        try:
            self._session.add(stock_group)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add stock group") from exc

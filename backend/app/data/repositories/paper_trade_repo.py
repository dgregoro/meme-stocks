from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.paper_trade import PaperTrade
from backend.app.utils.errors import DataAccessError


class PaperTradeRepository:
    """Data access for PaperTrade entities (simulated buy/sell transactions)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, trade: PaperTrade) -> None:
        """Persist a new paper trade. Caller must commit the session."""
        try:
            self._session.add(trade)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add paper trade") from exc

    def get(self, trade_id: int) -> PaperTrade | None:
        stmt = select(PaperTrade).where(PaperTrade.id == trade_id)
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to fetch paper trade") from exc

    def list(self) -> Sequence[PaperTrade]:
        """List all trades, most recent first (by entry_at)."""
        stmt = select(PaperTrade).order_by(PaperTrade.entry_at.desc())
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list paper trades") from exc

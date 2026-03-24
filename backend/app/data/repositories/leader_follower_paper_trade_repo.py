"""Repository for LeaderFollowerPaperTrade."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_paper_trade import LeaderFollowerPaperTrade
from backend.app.utils.errors import DataAccessError


class LeaderFollowerPaperTradeRepository:
    """Data access for paper trades."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, trade: LeaderFollowerPaperTrade) -> None:
        try:
            self._session.add(trade)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add paper trade") from exc

    def count_for_run(self, run_id: int) -> int:
        stmt = (
            select(func.count()).select_from(LeaderFollowerPaperTrade).where(LeaderFollowerPaperTrade.run_id == run_id)
        )
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count trades") from exc

    def list_for_run(self, run_id: int, offset: int = 0, limit: int = 100) -> Sequence[LeaderFollowerPaperTrade]:
        stmt = (
            select(LeaderFollowerPaperTrade)
            .where(LeaderFollowerPaperTrade.run_id == run_id)
            .order_by(LeaderFollowerPaperTrade.id.asc())
            .offset(offset)
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list trades") from exc

    def list_all_for_run_ordered(self, run_id: int) -> Sequence[LeaderFollowerPaperTrade]:
        stmt = (
            select(LeaderFollowerPaperTrade)
            .where(LeaderFollowerPaperTrade.run_id == run_id)
            .order_by(LeaderFollowerPaperTrade.id.asc())
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list trades") from exc

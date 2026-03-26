"""Repository for LeaderFollowerOptimizationResult."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_optimization_result import LeaderFollowerOptimizationResult
from backend.app.utils.errors import DataAccessError


class LeaderFollowerOptimizationResultRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(self, rows: Sequence[LeaderFollowerOptimizationResult]) -> None:
        try:
            self._session.add_all(rows)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add optimization results") from exc

    def list_top_for_run(self, run_id: int, limit: int) -> Sequence[LeaderFollowerOptimizationResult]:
        stmt = (
            select(LeaderFollowerOptimizationResult)
            .where(LeaderFollowerOptimizationResult.run_id == run_id)
            .order_by(LeaderFollowerOptimizationResult.rank)
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list optimization results") from exc

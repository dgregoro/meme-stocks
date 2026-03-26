"""Repository for LeaderFollowerOptimizationRun."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_optimization_run import LeaderFollowerOptimizationRun
from backend.app.utils.errors import DataAccessError


class LeaderFollowerOptimizationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: LeaderFollowerOptimizationRun) -> None:
        try:
            self._session.add(run)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add optimization run") from exc

    def get(self, run_id: int) -> LeaderFollowerOptimizationRun | None:
        try:
            return self._session.get(LeaderFollowerOptimizationRun, run_id)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get optimization run") from exc

    def list_recent(self, limit: int = 50) -> Sequence[LeaderFollowerOptimizationRun]:
        stmt = select(LeaderFollowerOptimizationRun).order_by(LeaderFollowerOptimizationRun.id.desc()).limit(limit)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list optimization runs") from exc

    def count_results_for_run(self, run_id: int) -> int:
        from backend.app.models.leader_follower_optimization_result import LeaderFollowerOptimizationResult

        stmt = (
            select(func.count())
            .select_from(LeaderFollowerOptimizationResult)
            .where(LeaderFollowerOptimizationResult.run_id == run_id)
        )
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count optimization results") from exc

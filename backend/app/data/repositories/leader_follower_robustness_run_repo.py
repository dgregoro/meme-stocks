"""Repository for LeaderFollowerRobustnessRun."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_robustness_aggregate import LeaderFollowerRobustnessAggregate
from backend.app.models.leader_follower_robustness_run import LeaderFollowerRobustnessRun
from backend.app.models.leader_follower_robustness_split_result import LeaderFollowerRobustnessSplitResult
from backend.app.utils.errors import DataAccessError


class LeaderFollowerRobustnessRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: LeaderFollowerRobustnessRun) -> None:
        try:
            self._session.add(run)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add robustness run") from exc

    def get(self, run_id: int) -> LeaderFollowerRobustnessRun | None:
        try:
            return self._session.get(LeaderFollowerRobustnessRun, run_id)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get robustness run") from exc

    def list_recent(self, limit: int = 50) -> Sequence[LeaderFollowerRobustnessRun]:
        stmt = select(LeaderFollowerRobustnessRun).order_by(LeaderFollowerRobustnessRun.id.desc()).limit(limit)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list robustness runs") from exc

    def count_split_results_for_run(self, run_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(LeaderFollowerRobustnessSplitResult)
            .where(LeaderFollowerRobustnessSplitResult.run_id == run_id)
        )
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count split results") from exc

    def count_aggregates_for_run(self, run_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(LeaderFollowerRobustnessAggregate)
            .where(LeaderFollowerRobustnessAggregate.run_id == run_id)
        )
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count aggregates") from exc

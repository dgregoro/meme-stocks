"""Repository for LeaderFollowerRobustnessAggregate."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_robustness_aggregate import LeaderFollowerRobustnessAggregate
from backend.app.utils.errors import DataAccessError


class LeaderFollowerRobustnessAggregateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(self, rows: Sequence[LeaderFollowerRobustnessAggregate]) -> None:
        try:
            self._session.add_all(rows)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add robustness aggregates") from exc

    def list_top_for_run(self, run_id: int, limit: int) -> Sequence[LeaderFollowerRobustnessAggregate]:
        stmt = (
            select(LeaderFollowerRobustnessAggregate)
            .where(LeaderFollowerRobustnessAggregate.run_id == run_id)
            .order_by(LeaderFollowerRobustnessAggregate.rank)
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list robustness aggregates") from exc

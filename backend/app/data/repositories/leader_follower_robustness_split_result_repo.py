"""Repository for LeaderFollowerRobustnessSplitResult."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_robustness_split_result import LeaderFollowerRobustnessSplitResult
from backend.app.utils.errors import DataAccessError


class LeaderFollowerRobustnessSplitResultRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(self, rows: Sequence[LeaderFollowerRobustnessSplitResult]) -> None:
        try:
            self._session.add_all(rows)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add split results") from exc

    def list_for_run(
        self,
        run_id: int,
        *,
        limit: int,
        offset: int,
        config_hash: str | None = None,
        split_index: int | None = None,
    ) -> Sequence[LeaderFollowerRobustnessSplitResult]:
        stmt = select(LeaderFollowerRobustnessSplitResult).where(LeaderFollowerRobustnessSplitResult.run_id == run_id)
        if config_hash is not None:
            stmt = stmt.where(LeaderFollowerRobustnessSplitResult.config_hash == config_hash)
        if split_index is not None:
            stmt = stmt.where(LeaderFollowerRobustnessSplitResult.split_index == split_index)
        stmt = (
            stmt.order_by(LeaderFollowerRobustnessSplitResult.split_index, LeaderFollowerRobustnessSplitResult.id)
            .offset(offset)
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list split results") from exc

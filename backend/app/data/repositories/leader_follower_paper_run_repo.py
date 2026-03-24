"""Repository for LeaderFollowerPaperRun."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_paper_run import LeaderFollowerPaperRun
from backend.app.utils.errors import DataAccessError


class LeaderFollowerPaperRunRepository:
    """Data access for paper trading runs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: LeaderFollowerPaperRun) -> None:
        try:
            self._session.add(run)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add paper run") from exc

    def get(self, run_id: int) -> LeaderFollowerPaperRun | None:
        try:
            return self._session.get(LeaderFollowerPaperRun, run_id)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to get paper run") from exc

    def list_recent(self, limit: int = 50) -> Sequence[LeaderFollowerPaperRun]:
        stmt = select(LeaderFollowerPaperRun).order_by(LeaderFollowerPaperRun.id.desc()).limit(limit)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list paper runs") from exc

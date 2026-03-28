"""Repository for LeaderDebugEvaluation (symbol-level leader detection debug data)."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.utils.errors import DataAccessError


class LeaderDebugRepository:
    """Data access for LeaderDebugEvaluation entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, evaluation: LeaderDebugEvaluation) -> None:
        """Persist a LeaderDebugEvaluation. Caller must commit the session."""
        try:
            self._session.add(evaluation)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add leader debug evaluation") from exc

    def list_by_run_id(
        self,
        run_id: int,
        limit: int = 50,
    ) -> Sequence[LeaderDebugEvaluation]:
        """List evaluations for a run, ordered by symbol."""
        stmt = (
            select(LeaderDebugEvaluation)
            .where(LeaderDebugEvaluation.job_run_id == run_id)
            .order_by(LeaderDebugEvaluation.stock_symbol)
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list leader debug evaluations") from exc

    def list_near_misses_by_run_id(
        self,
        run_id: int,
        limit: int = 20,
    ) -> Sequence[LeaderDebugEvaluation]:
        """List near-miss evaluations (non-qualified with return_pct and volume_ratio).
        Rank by proximity: symbols with return_pct and volume_ratio that failed on
        thresholds only. Order by descending min(return_ratio, volume_ratio) as
        proxy for proximity (higher = closer to qualifying).
        """
        stmt = (
            select(LeaderDebugEvaluation)
            .where(
                LeaderDebugEvaluation.job_run_id == run_id,
                LeaderDebugEvaluation.qualified_as_leader.is_(False),
                LeaderDebugEvaluation.return_pct.isnot(None),
                LeaderDebugEvaluation.volume_ratio.isnot(None),
            )
            .order_by(
                func.abs(LeaderDebugEvaluation.return_pct).desc(),
                LeaderDebugEvaluation.volume_ratio.desc(),
            )
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list leader near-misses") from exc

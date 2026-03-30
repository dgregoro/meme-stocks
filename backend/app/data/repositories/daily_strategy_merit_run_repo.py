"""Repository for persisted daily-strategy merit runs."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.daily_strategy_merit_run import DailyStrategyMeritRun
from backend.app.utils.errors import DataAccessError


class DailyStrategyMeritRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: DailyStrategyMeritRun) -> DailyStrategyMeritRun:
        try:
            self._session.add(row)
            self._session.flush()
            return row
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to insert daily_strategy_merit_run") from exc

    def get(self, run_id: int) -> DailyStrategyMeritRun | None:
        try:
            return self._session.get(DailyStrategyMeritRun, run_id)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to load daily_strategy_merit_run") from exc

    def list_recent(self, *, limit: int = 50) -> list[DailyStrategyMeritRun]:
        lim = max(1, min(int(limit), 500))
        stmt: Select[tuple[DailyStrategyMeritRun]] = (
            select(DailyStrategyMeritRun).order_by(DailyStrategyMeritRun.id.desc()).limit(lim)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list daily_strategy_merit_runs") from exc

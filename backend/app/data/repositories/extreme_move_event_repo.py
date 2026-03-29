"""Repository for extreme move research events (016)."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.utils.errors import DataAccessError


class ExtremeMoveEventRepository:
    """CRUD and queries for ExtremeMoveEvent."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, event: ExtremeMoveEvent) -> None:
        """Insert or update row for (symbol, event_date). Preserves original created_at on update."""
        stmt = select(ExtremeMoveEvent).where(
            ExtremeMoveEvent.symbol == event.symbol,
            ExtremeMoveEvent.event_date == event.event_date,
        )
        try:
            existing = self._session.execute(stmt).scalar_one_or_none()
            if existing is not None:
                existing.return_pct = event.return_pct
                existing.event_type = event.event_type
                existing.magnitude_bucket = event.magnitude_bucket
                existing.volume_ratio = event.volume_ratio
                existing.volume_bucket = event.volume_bucket
            else:
                self._session.add(event)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to upsert extreme move event") from exc

    def delete_in_date_range(
        self,
        start_date: date,
        end_date: date,
        symbols: Sequence[str] | None = None,
    ) -> int:
        stmt = delete(ExtremeMoveEvent).where(
            ExtremeMoveEvent.event_date >= start_date,
            ExtremeMoveEvent.event_date <= end_date,
        )
        if symbols:
            stmt = stmt.where(ExtremeMoveEvent.symbol.in_(tuple(symbols)))
        try:
            res = self._session.execute(stmt)
            return int(res.rowcount or 0)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to delete extreme move events in range") from exc

    def _filtered_select(
        self,
        symbol: str | None,
        since_date: date | None,
        until_date: date | None,
        event_type: str | None,
    ) -> Select[tuple[ExtremeMoveEvent]]:
        stmt = select(ExtremeMoveEvent)
        if symbol:
            stmt = stmt.where(ExtremeMoveEvent.symbol == symbol)
        if since_date is not None:
            stmt = stmt.where(ExtremeMoveEvent.event_date >= since_date)
        if until_date is not None:
            stmt = stmt.where(ExtremeMoveEvent.event_date <= until_date)
        if event_type:
            stmt = stmt.where(ExtremeMoveEvent.event_type == event_type)
        return stmt

    def count_filtered(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        event_type: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(ExtremeMoveEvent)
        if symbol:
            stmt = stmt.where(ExtremeMoveEvent.symbol == symbol)
        if since_date is not None:
            stmt = stmt.where(ExtremeMoveEvent.event_date >= since_date)
        if until_date is not None:
            stmt = stmt.where(ExtremeMoveEvent.event_date <= until_date)
        if event_type:
            stmt = stmt.where(ExtremeMoveEvent.event_type == event_type)
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count extreme move events") from exc

    def list_filtered(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtremeMoveEvent]:
        stmt = (
            self._filtered_select(symbol, since_date, until_date, event_type)
            .order_by(ExtremeMoveEvent.event_date.desc(), ExtremeMoveEvent.symbol.asc())
            .limit(limit)
            .offset(offset)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list extreme move events") from exc

    def list_for_evaluation(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        limit: int = 500,
    ) -> list[ExtremeMoveEvent]:
        stmt = self._filtered_select(symbol, since_date, until_date, None).order_by(
            ExtremeMoveEvent.event_date.asc(), ExtremeMoveEvent.id.asc()
        )
        stmt = stmt.limit(limit)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list extreme move events for evaluation") from exc

"""Repository for volume spike research events."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence, cast

from sqlalchemy import Select, delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.volume_spike_event import VolumeSpikeEvent
from backend.app.utils.errors import DataAccessError


class VolumeSpikeEventRepository:
    """CRUD and queries for VolumeSpikeEvent."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, event: VolumeSpikeEvent) -> None:
        """Insert or update row for (symbol, event_date). Preserves original created_at on update."""
        stmt = select(VolumeSpikeEvent).where(
            VolumeSpikeEvent.symbol == event.symbol,
            VolumeSpikeEvent.event_date == event.event_date,
        )
        try:
            existing = self._session.execute(stmt).scalar_one_or_none()
            if existing is not None:
                existing.volume = event.volume
                existing.baseline_volume = event.baseline_volume
                existing.volume_ratio = event.volume_ratio
                existing.same_day_return_pct = event.same_day_return_pct
                existing.event_type = event.event_type
            else:
                self._session.add(event)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to upsert volume spike event") from exc

    def delete_in_date_range(
        self,
        start_date: date,
        end_date: date,
        symbols: Sequence[str] | None = None,
    ) -> int:
        """Delete events with event_date in [start_date, end_date]. Returns rows deleted."""
        stmt = delete(VolumeSpikeEvent).where(
            VolumeSpikeEvent.event_date >= start_date,
            VolumeSpikeEvent.event_date <= end_date,
        )
        if symbols:
            stmt = stmt.where(VolumeSpikeEvent.symbol.in_(tuple(symbols)))
        try:
            res = cast(CursorResult[Any], self._session.execute(stmt))
            return int(res.rowcount or 0)
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to delete volume spike events in range") from exc

    def _filtered_select(
        self,
        symbol: str | None,
        since_date: date | None,
        until_date: date | None,
        event_type: str | None,
    ) -> Select[tuple[VolumeSpikeEvent]]:
        stmt = select(VolumeSpikeEvent)
        if symbol:
            stmt = stmt.where(VolumeSpikeEvent.symbol == symbol)
        if since_date is not None:
            stmt = stmt.where(VolumeSpikeEvent.event_date >= since_date)
        if until_date is not None:
            stmt = stmt.where(VolumeSpikeEvent.event_date <= until_date)
        if event_type:
            stmt = stmt.where(VolumeSpikeEvent.event_type == event_type)
        return stmt

    def count_filtered(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        event_type: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(VolumeSpikeEvent)
        if symbol:
            stmt = stmt.where(VolumeSpikeEvent.symbol == symbol)
        if since_date is not None:
            stmt = stmt.where(VolumeSpikeEvent.event_date >= since_date)
        if until_date is not None:
            stmt = stmt.where(VolumeSpikeEvent.event_date <= until_date)
        if event_type:
            stmt = stmt.where(VolumeSpikeEvent.event_type == event_type)
        try:
            return int(self._session.execute(stmt).scalar_one())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count volume spike events") from exc

    def list_filtered(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[VolumeSpikeEvent]:
        stmt = (
            self._filtered_select(symbol, since_date, until_date, event_type)
            .order_by(VolumeSpikeEvent.event_date.desc(), VolumeSpikeEvent.symbol.asc())
            .limit(limit)
            .offset(offset)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list volume spike events") from exc

    def list_for_evaluation(
        self,
        symbol: str | None = None,
        since_date: date | None = None,
        until_date: date | None = None,
        limit: int = 500,
    ) -> list[VolumeSpikeEvent]:
        """Load events for evaluation (no event_type filter; chronological)."""
        stmt = self._filtered_select(symbol, since_date, until_date, None).order_by(
            VolumeSpikeEvent.event_date.asc(), VolumeSpikeEvent.id.asc()
        )
        stmt = stmt.limit(limit)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list volume spike events for evaluation") from exc

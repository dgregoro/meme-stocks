"""Repository for LeaderEvent (detected significant moves)."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_event import LeaderEvent
from backend.app.utils.errors import DataAccessError


class LeaderEventRepository:
    """Data access for LeaderEvent entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: LeaderEvent) -> None:
        """Persist a LeaderEvent. Caller must commit the session."""
        try:
            self._session.add(event)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add leader event") from exc

    def list_by_date(self, event_date: dt.date) -> Sequence[LeaderEvent]:
        """List leader events for a given date."""
        stmt = (
            select(LeaderEvent)
            .where(LeaderEvent.event_date == event_date)
            .order_by(LeaderEvent.leader_symbol)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list leader events by date") from exc

    def list_recent(self, limit: int = 100) -> Sequence[LeaderEvent]:
        """List most recent leader events, newest first."""
        stmt = (
            select(LeaderEvent)
            .order_by(LeaderEvent.event_date.desc(), LeaderEvent.created_at.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list recent leader events") from exc

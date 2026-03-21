"""Repository for LeaderFollowerCandidate (follower candidates from detection runs)."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_candidate import LeaderFollowerCandidate
from backend.app.utils.errors import DataAccessError


class LeaderFollowerCandidateRepository:
    """Data access for LeaderFollowerCandidate entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, candidate: LeaderFollowerCandidate) -> None:
        """Persist a LeaderFollowerCandidate. Caller must commit the session."""
        try:
            self._session.add(candidate)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add leader follower candidate") from exc

    def list_recent(
        self,
        limit: int = 100,
        since_date: dt.date | None = None,
        leader: str | None = None,
        follower: str | None = None,
        run_id: int | None = None,
    ) -> Sequence[LeaderFollowerCandidate]:
        """List most recent follower candidates, newest first. Optional filters."""
        stmt = (
            select(LeaderFollowerCandidate)
            .order_by(
                LeaderFollowerCandidate.event_date.desc(),
                LeaderFollowerCandidate.created_at.desc(),
            )
            .limit(limit)
        )
        if since_date is not None:
            stmt = stmt.where(LeaderFollowerCandidate.event_date >= since_date)
        if leader is not None:
            stmt = stmt.where(LeaderFollowerCandidate.leader_symbol == leader)
        if follower is not None:
            stmt = stmt.where(LeaderFollowerCandidate.follower_symbol == follower)
        if run_id is not None:
            stmt = stmt.where(LeaderFollowerCandidate.job_run_id == run_id)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list recent follower candidates") from exc

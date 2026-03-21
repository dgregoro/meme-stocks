"""Repository for LeaderFollowerSignal (follower opportunity signals)."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.utils.errors import DataAccessError


class LeaderFollowerSignalRepository:
    """Data access for LeaderFollowerSignal entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, signal: LeaderFollowerSignal) -> None:
        """Persist a LeaderFollowerSignal. Caller must commit the session."""
        try:
            self._session.add(signal)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add leader follower signal") from exc

    def exists_within_cooldown(
        self,
        leader_symbol: str,
        follower_symbol: str,
        since_date: dt.date,
        cooldown_days: int,
    ) -> bool:
        """Return True if a signal for (leader, follower) exists within cooldown window.

        Cooldown: signals with signal_date >= (since_date - cooldown_days) are considered
        within window. For 1-day cooldown, we check if any signal exists on or after
        (since_date - 1 day).
        """
        from datetime import timedelta

        cutoff = since_date - timedelta(days=cooldown_days)
        stmt = (
            select(LeaderFollowerSignal.id)
            .where(
                and_(
                    LeaderFollowerSignal.leader_symbol == leader_symbol,
                    LeaderFollowerSignal.follower_symbol == follower_symbol,
                    LeaderFollowerSignal.signal_date >= cutoff,
                )
            )
            .limit(1)
        )
        try:
            row = self._session.execute(stmt).scalar_one_or_none()
            return row is not None
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to check cooldown") from exc

    def list_signals(
        self,
        limit: int = 50,
        since_date: dt.date | None = None,
        leader: str | None = None,
        group: str | None = None,
    ) -> Sequence[LeaderFollowerSignal]:
        """List signals with optional filters. Ordered by signal_date desc, created_at desc."""
        stmt = (
            select(LeaderFollowerSignal)
            .order_by(
                LeaderFollowerSignal.signal_date.desc(),
                LeaderFollowerSignal.created_at.desc(),
            )
            .limit(limit)
        )
        if since_date is not None:
            stmt = stmt.where(LeaderFollowerSignal.signal_date >= since_date)
        if leader is not None:
            stmt = stmt.where(LeaderFollowerSignal.leader_symbol == leader)
        if group is not None:
            stmt = stmt.where(LeaderFollowerSignal.group_id == group)
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list signals") from exc

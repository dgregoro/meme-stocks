from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.reddit_post import RedditPost
from backend.app.utils.errors import DataAccessError


class RedditPostRepository:
    """Repository for RedditPost entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, post: RedditPost) -> None:
        try:
            self._session.add(post)
            self._session.flush()
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to add reddit post") from exc

    def list_for_stock(self, symbol: str, since: datetime | None = None) -> Sequence[RedditPost]:
        stmt = select(RedditPost).where(RedditPost.stock_symbol == symbol)
        if since is not None:
            stmt = stmt.where(RedditPost.collected_at >= since)
        stmt = stmt.order_by(RedditPost.collected_at.desc())

        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to list reddit posts") from exc

    def count_recent_mentions(self, symbol: str, window: timedelta) -> int:
        cutoff = datetime.utcnow() - window
        stmt = select(RedditPost).where(
            RedditPost.stock_symbol == symbol,
            RedditPost.collected_at >= cutoff,
        )
        try:
            # SQLAlchemy 2.x ScalarResult does not expose .count(); materialize
            # and count explicitly. For expected data volumes this is fine,
            # and keeps behavior explicit and testable.
            return len(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:  # pragma: no cover
            raise DataAccessError("Failed to count reddit mentions") from exc

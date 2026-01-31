from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.reddit_post import RedditPost
from backend.app.utils.errors import DataAccessError


class RedditPostRepository:
    """Repository for RedditPost entities.

    Note: Posts are now separate from symbol mentions. Use RedditSymbolMentionRepository
    to query posts by symbol.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, post_id: str) -> RedditPost | None:
        """Get a post by ID."""
        try:
            stmt = select(RedditPost).where(RedditPost.id == post_id)
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to get post {post_id}") from exc

    def add(self, post: RedditPost) -> None:
        """Add a new post."""
        try:
            self._session.add(post)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to add reddit post") from exc

    def list_recent(
        self, limit: int = 100, since: datetime | None = None
    ) -> Sequence[RedditPost]:
        """List recent posts, optionally filtered by collection time.

        Args:
            limit: Maximum number of posts to return
            since: Optional datetime to filter posts collected after this time

        Returns:
            Sequence of RedditPost objects
        """
        stmt = select(RedditPost)
        if since is not None:
            stmt = stmt.where(RedditPost.collected_at >= since)
        stmt = stmt.order_by(RedditPost.collected_at.desc()).limit(limit)

        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError("Failed to list reddit posts") from exc

    def list_for_stock(
        self, symbol: str, since: datetime | None = None
    ) -> Sequence[RedditPost]:
        """Get posts that mention a symbol (via symbol mentions table).

        This method maintains backward compatibility but now uses the
        symbol mentions junction table.

        Args:
            symbol: Stock symbol to search for
            since: Optional datetime to filter posts collected after this time

        Returns:
            Sequence of RedditPost objects
        """
        from backend.app.models.reddit_symbol_mention import RedditSymbolMention

        stmt = (
            select(RedditPost)
            .join(RedditSymbolMention, RedditPost.id == RedditSymbolMention.post_id)
            .where(RedditSymbolMention.symbol == symbol)
        )

        if since is not None:
            stmt = stmt.where(RedditPost.collected_at >= since)

        stmt = stmt.order_by(RedditPost.collected_at.desc())

        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to list posts for symbol {symbol}") from exc

    def count_recent_mentions(self, symbol: str, window: timedelta) -> int:
        """Count recent mentions of a symbol (backward compatibility).

        This method delegates to RedditSymbolMentionRepository for the actual count.
        """
        from backend.app.data.repositories.reddit_symbol_mention_repo import (
            RedditSymbolMentionRepository,
        )

        mention_repo = RedditSymbolMentionRepository(self._session)
        return mention_repo.count_recent_mentions(symbol, window)

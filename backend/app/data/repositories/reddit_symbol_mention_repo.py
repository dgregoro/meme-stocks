from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.utils.errors import DataAccessError


class RedditSymbolMentionRepository:
    """Repository for RedditSymbolMention entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, mention: RedditSymbolMention) -> None:
        """Add a symbol mention."""
        try:
            self._session.add(mention)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to add symbol mention") from exc

    def get_posts_for_symbol(
        self, symbol: str, since: datetime | None = None
    ) -> Sequence[RedditSymbolMention]:
        """Get all posts that mention a symbol.

        Args:
            symbol: Stock symbol to search for
            since: Optional datetime to filter posts collected after this time

        Returns:
            Sequence of RedditSymbolMention objects with post relationships loaded
        """
        from backend.app.models.reddit_post import RedditPost

        stmt = (
            select(RedditSymbolMention)
            .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
            .where(RedditSymbolMention.symbol == symbol)
        )

        if since is not None:
            stmt = stmt.where(RedditPost.collected_at >= since)

        stmt = stmt.order_by(RedditPost.collected_at.desc())

        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to get posts for symbol {symbol}") from exc

    def count_recent_mentions(self, symbol: str, window: timedelta) -> int:
        """Count recent mentions of a symbol within a time window."""
        from backend.app.models.reddit_post import RedditPost

        cutoff = datetime.now(timezone.utc) - window
        stmt = (
            select(RedditSymbolMention)
            .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
            .where(
                RedditSymbolMention.symbol == symbol,
                RedditPost.collected_at >= cutoff,
            )
        )

        try:
            return len(list(self._session.execute(stmt).scalars().all()))
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to count mentions for {symbol}") from exc

    def get_symbols_for_post(self, post_id: str) -> Sequence[str]:
        """Get all symbols mentioned in a post.

        Args:
            post_id: Reddit post ID

        Returns:
            Sequence of symbol strings
        """
        stmt = select(RedditSymbolMention.symbol).where(
            RedditSymbolMention.post_id == post_id
        )

        try:
            return [row[0] for row in self._session.execute(stmt).all()]
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to get symbols for post {post_id}") from exc


"""Repository for RedditDailyFeature: daily Reddit aggregates per (symbol, trading_day)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models.reddit_daily_feature import RedditDailyFeature
from backend.app.utils.errors import DataAccessError


class RedditDailyFeatureRepository:
    """Data access for reddit_daily_features table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, symbol: str, trading_day: date) -> RedditDailyFeature | None:
        """Return the row for (symbol, trading_day) or None."""
        stmt = select(RedditDailyFeature).where(
            RedditDailyFeature.symbol == symbol,
            RedditDailyFeature.trading_day == trading_day,
        )
        try:
            return self._session.execute(stmt).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to get reddit daily feature for {symbol} @ {trading_day}") from exc

    def upsert(self, feature: RedditDailyFeature) -> None:
        """Insert or update: if (symbol, trading_day) exists, update numeric fields and updated_at."""
        existing = self.get(feature.symbol, feature.trading_day)
        try:
            if existing is not None:
                existing.mention_count = feature.mention_count
                existing.unique_authors = feature.unique_authors
                existing.total_upvotes = feature.total_upvotes
                existing.total_comments = feature.total_comments
                existing.upvote_weighted_mentions = feature.upvote_weighted_mentions
                existing.updated_at = datetime.now(timezone.utc)
                self._session.flush()
            else:
                self._session.add(feature)
                self._session.flush()
        except SQLAlchemyError as exc:
            raise DataAccessError(
                f"Failed to upsert reddit daily feature for {feature.symbol} @ {feature.trading_day}"
            ) from exc

    def list_for_symbol(self, symbol: str, start_day: date, end_day: date) -> Sequence[RedditDailyFeature]:
        """Return all rows for symbol in [start_day, end_day] inclusive, ordered by trading_day."""
        stmt = (
            select(RedditDailyFeature)
            .where(
                RedditDailyFeature.symbol == symbol,
                RedditDailyFeature.trading_day >= start_day,
                RedditDailyFeature.trading_day <= end_day,
            )
            .order_by(RedditDailyFeature.trading_day)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to list reddit daily features for {symbol}") from exc

    def list_for_day(self, trading_day: date) -> Sequence[RedditDailyFeature]:
        """Return all rows for the given trading day."""
        stmt = (
            select(RedditDailyFeature)
            .where(RedditDailyFeature.trading_day == trading_day)
            .order_by(RedditDailyFeature.symbol)
        )
        try:
            return list(self._session.execute(stmt).scalars().all())
        except SQLAlchemyError as exc:
            raise DataAccessError(f"Failed to list reddit daily features for day {trading_day}") from exc

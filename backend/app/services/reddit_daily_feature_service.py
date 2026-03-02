"""Aggregate Reddit posts into daily features per (symbol, trading_day) for causal research.

Uses posted_at (not collected_at) with configurable after-hours and weekend rules.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import log10
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.reddit_daily_feature_repo import RedditDailyFeatureRepository
from backend.app.models.reddit_daily_feature import RedditDailyFeature
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention

logger = logging.getLogger(__name__)


def effective_trading_day(
    posted_at: datetime,
    *,
    market_timezone: str = "America/New_York",
    market_close_hour_local: int = 16,
    market_close_minute_local: int = 0,
) -> date:
    """Assign a post to a trading day using posted_at, after-hours and weekend rules.

    - Convert posted_at to market timezone.
    - If local time >= market_close_hour_local, count toward next calendar day.
    - If the resulting date is Saturday or Sunday, roll forward to next Monday.

    Returns:
        The trading day (date) this post belongs to.
    """
    tz = ZoneInfo(market_timezone)
    # Ensure we have a timezone-aware datetime (treat naive as UTC)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    local_dt = posted_at.astimezone(tz)
    effective = local_dt.date()

    cutoff_local = time(hour=market_close_hour_local, minute=market_close_minute_local)
    local_time = local_dt.timetz().replace(tzinfo=None)
    if local_time >= cutoff_local:
        effective += timedelta(days=1)
    # Weekend: Sat (5) -> Monday (+2), Sun (6) -> Monday (+1)
    if effective.weekday() == 5:
        effective += timedelta(days=2)
    elif effective.weekday() == 6:
        effective += timedelta(days=1)
    return effective


@dataclass
class _DailyAggregate:
    """In-memory aggregate for a single (symbol, trading_day)."""

    post_ids: set[str]
    authors: set[str]
    total_upvotes: int
    total_comments: int
    upvote_weighted_mentions: float


def compute_and_store_reddit_daily_features(
    db: Session,
    start_day: date,
    end_day: date,
) -> dict[str, int | str]:
    """Compute daily Reddit aggregates for [start_day, end_day] and persist them.

    Uses posted_at only. After-hours and weekend rules are applied via effective_trading_day.
    Returns a small stats dict: rows_upserted, symbols_seen, date_range, etc.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.market_timezone)
    # Query window: posts that can contribute to start_day..end_day after applying
    # after-hours + weekend rules. Use a small buffer *before* and *after* the range
    # so that posts whose effective_trading_day falls inside [start_day, end_day]
    # are not missed.
    window_start_local = datetime.combine(start_day - timedelta(days=3), time.min)
    window_end_local = datetime.combine(end_day + timedelta(days=1), time.max).replace(microsecond=999999)
    window_start_utc = window_start_local.replace(tzinfo=tz).astimezone(timezone.utc)
    window_end_utc = window_end_local.replace(tzinfo=tz).astimezone(timezone.utc)

    stmt = (
        select(
            RedditSymbolMention.symbol,
            RedditSymbolMention.post_id,
            RedditPost.posted_at,
            RedditPost.author,
            RedditPost.upvotes,
            RedditPost.comments,
        )
        .join(RedditPost, RedditSymbolMention.post_id == RedditPost.id)
        .where(
            RedditPost.posted_at >= window_start_utc,
            RedditPost.posted_at <= window_end_utc,
        )
    )
    rows = list(db.execute(stmt).all())

    # Aggregate per (symbol, effective_trading_day)
    agg: dict[tuple[str, date], _DailyAggregate] = defaultdict(lambda: _DailyAggregate(set(), set(), 0, 0, 0.0))
    for symbol, post_id, posted_at, author, upvotes, comments in rows:
        if posted_at is None:
            continue
        eff = effective_trading_day(
            posted_at,
            market_timezone=settings.market_timezone,
            market_close_hour_local=settings.market_close_hour_local,
            market_close_minute_local=getattr(settings, "market_close_minute_local", 0),
        )
        if eff < start_day or eff > end_day:
            continue
        entry = agg[(symbol, eff)]
        if post_id not in entry.post_ids:
            entry.post_ids.add(post_id)
            entry.total_upvotes += upvotes or 0
            entry.total_comments += comments or 0
            entry.upvote_weighted_mentions += log10((upvotes or 0) + (comments or 0) + 1)
        if author:
            entry.authors.add(author)

    repo = RedditDailyFeatureRepository(db)
    rows_upserted = 0
    for (symbol, trading_day), entry in agg.items():
        feature = RedditDailyFeature(
            symbol=symbol,
            trading_day=trading_day,
            mention_count=len(entry.post_ids),
            unique_authors=len(entry.authors),
            total_upvotes=entry.total_upvotes,
            total_comments=entry.total_comments,
            upvote_weighted_mentions=round(entry.upvote_weighted_mentions, 6),
        )
        repo.upsert(feature)
        rows_upserted += 1

    symbols_seen = len({s for s, _ in agg})
    logger.info(
        "Reddit daily features: start=%s end=%s rows_upserted=%s symbols=%s post_rows=%s",
        start_day,
        end_day,
        rows_upserted,
        symbols_seen,
        len(rows),
    )
    return {
        "start_day": str(start_day),
        "end_day": str(end_day),
        "rows_upserted": rows_upserted,
        "symbols_seen": symbols_seen,
        "post_rows_queried": len(rows),
    }

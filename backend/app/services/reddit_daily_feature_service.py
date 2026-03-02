"""Aggregate Reddit posts into daily features per (symbol, trading_day) for causal research.

Uses posted_at (not collected_at) with configurable after-hours and weekend rules.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
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
) -> date:
    """Assign a post to a trading day using posted_at, after-hours and weekend rules.

    - Convert posted_at to market timezone.
    - If local time >= market_close_hour_local, count toward next calendar day.
    - If the resulting date is Saturday or Sunday, roll forward to next Monday.

    Returns:
        The trading day (date) this post belongs to.
    """
    tz = ZoneInfo(market_timezone)
    # Ensure we have a timezone-aware datetime
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    local_dt = posted_at.astimezone(tz)
    effective = local_dt.date()
    if local_dt.hour >= market_close_hour_local:
        effective += timedelta(days=1)
    # Weekend: Sat (5) -> Monday (+2), Sun (6) -> Monday (+1)
    if effective.weekday() == 5:
        effective += timedelta(days=2)
    elif effective.weekday() == 6:
        effective += timedelta(days=1)
    return effective


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
    # Query window: posts that can contribute to start_day..end_day
    # From (start_day - 1) 00:00 local to end_day 23:59 local (inclusive)
    window_start_local = datetime.combine(start_day - timedelta(days=1), datetime.min.time())
    window_end_local = datetime.combine(end_day, datetime.max.time()).replace(microsecond=999999)
    window_start_utc = window_start_local.replace(tzinfo=tz).astimezone(timezone.utc)
    window_end_utc = window_end_local.replace(tzinfo=tz).astimezone(timezone.utc)

    stmt = (
        select(
            RedditSymbolMention.symbol,
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
    # Value: (mention_count, set(authors), total_upvotes, total_comments, sum(log10(upvotes+comments+1)))
    agg: dict[tuple[str, date], tuple[int, set[str], int, int, float]] = defaultdict(lambda: (0, set(), 0, 0, 0.0))
    for symbol, posted_at, author, upvotes, comments in rows:
        if posted_at is None:
            continue
        eff = effective_trading_day(
            posted_at,
            market_timezone=settings.market_timezone,
            market_close_hour_local=settings.market_close_hour_local,
        )
        if eff < start_day or eff > end_day:
            continue
        cnt, authors, tot_u, tot_c, weighted = agg[(symbol, eff)]
        cnt += 1
        if author:
            authors.add(author)
        tot_u += upvotes or 0
        tot_c += comments or 0
        weighted += log10((upvotes or 0) + (comments or 0) + 1)
        agg[(symbol, eff)] = (cnt, authors, tot_u, tot_c, weighted)

    repo = RedditDailyFeatureRepository(db)
    rows_upserted = 0
    for (symbol, trading_day), (
        mention_count,
        authors,
        total_upvotes,
        total_comments,
        upvote_weighted_mentions,
    ) in agg.items():
        feature = RedditDailyFeature(
            symbol=symbol,
            trading_day=trading_day,
            mention_count=mention_count,
            unique_authors=len(authors),
            total_upvotes=total_upvotes,
            total_comments=total_comments,
            upvote_weighted_mentions=round(upvote_weighted_mentions, 6),
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

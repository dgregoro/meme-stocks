"""Tests for Reddit daily feature aggregation: trading-day logic and persistence."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import reddit_daily_feature  # noqa: F401
from backend.app.models import reddit_post  # noqa: F401
from backend.app.models import reddit_symbol_mention  # noqa: F401
from backend.app.models import stock  # noqa: F401
from backend.app.services.reddit_daily_feature_service import (
    compute_and_store_reddit_daily_features,
    effective_trading_day,
)


# --- Unit tests: effective_trading_day ---


@pytest.mark.unit
def test_effective_trading_day_1559_et_same_day() -> None:
    """Posted at 15:59 ET stays on same calendar day (before market close)."""
    et = ZoneInfo("America/New_York")
    # Monday 2026-03-02 15:59 ET
    posted_at = datetime(2026, 3, 2, 15, 59, 0, tzinfo=et)
    got = effective_trading_day(posted_at, market_timezone="America/New_York", market_close_hour_local=16)
    assert got == date(2026, 3, 2)


@pytest.mark.unit
def test_effective_trading_day_1600_et_next_day() -> None:
    """Posted at 16:00 ET counts toward next calendar day."""
    et = ZoneInfo("America/New_York")
    posted_at = datetime(2026, 3, 2, 16, 0, 0, tzinfo=et)
    got = effective_trading_day(posted_at, market_timezone="America/New_York", market_close_hour_local=16)
    assert got == date(2026, 3, 3)


@pytest.mark.unit
def test_effective_trading_day_weekend_roll_friday_after_close() -> None:
    """Friday 16:00 ET -> next day Saturday -> roll forward to Monday."""
    et = ZoneInfo("America/New_York")
    # Friday 2026-02-27 16:00 ET -> effective_date = Saturday 2026-02-28 -> Monday 2026-03-02
    posted_at = datetime(2026, 2, 27, 16, 0, 0, tzinfo=et)
    got = effective_trading_day(posted_at, market_timezone="America/New_York", market_close_hour_local=16)
    assert got == date(2026, 3, 2)


@pytest.mark.unit
def test_effective_trading_day_accepts_utc_naive() -> None:
    """effective_trading_day accepts UTC-naive datetime (treats as UTC)."""
    # Naive 21:00 interpreted as UTC = 16:00 ET (EST) -> next day
    posted_at = datetime(2026, 3, 2, 21, 0, 0)  # no tzinfo
    got = effective_trading_day(posted_at, market_timezone="America/New_York", market_close_hour_local=16)
    assert got == date(2026, 3, 3)


# --- Integration tests: persistence and upsert ---


@pytest.mark.integration
def test_compute_and_store_persistence_and_upsert() -> None:
    """Running aggregation twice for same (symbol, day) updates row instead of duplicating."""
    from backend.app.data.repositories.reddit_daily_feature_repo import RedditDailyFeatureRepository
    from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
    from backend.app.data.repositories.reddit_symbol_mention_repo import RedditSymbolMentionRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.reddit_post import RedditPost
    from backend.app.models.reddit_symbol_mention import RedditSymbolMention
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        post_repo = RedditPostRepository(db)
        mention_repo = RedditSymbolMentionRepository(db)
        feature_repo = RedditDailyFeatureRepository(db)

        # One stock
        stock_repo.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
        db.flush()

        # Post on 2026-03-02 15:00 ET (same trading day 2026-03-02)
        et = ZoneInfo("America/New_York")
        posted_at = datetime(2026, 3, 2, 15, 0, 0, tzinfo=et)
        post = RedditPost(
            id="post1",
            subreddit="wallstreetbets",
            title="GME to the moon",
            author="u1",
            upvotes=10,
            comments=2,
            url="https://reddit.com/...",
            posted_at=posted_at,
        )
        post_repo.add(post)
        mention_repo.add(RedditSymbolMention(post_id="post1", symbol="GME"))
        db.commit()

        # Compute for range including 2026-03-02
        stats = compute_and_store_reddit_daily_features(db, date(2026, 3, 1), date(2026, 3, 5))
        db.commit()
        assert stats["rows_upserted"] == 1
        row = feature_repo.get("GME", date(2026, 3, 2))
        assert row is not None
        assert row.mention_count == 1
        assert row.unique_authors == 1
        assert row.upvote_weighted_mentions > 0

        # Run again (idempotent): same row updated, no duplicate
        stats2 = compute_and_store_reddit_daily_features(db, date(2026, 3, 1), date(2026, 3, 5))
        db.commit()
        assert stats2["rows_upserted"] == 1
        rows = feature_repo.list_for_day(date(2026, 3, 2))
        assert len(rows) == 1
        assert rows[0].symbol == "GME"
        assert rows[0].mention_count == 1
    finally:
        db.close()


@pytest.mark.integration
def test_friday_after_close_counts_toward_monday_effective_day() -> None:
    """Post Friday after market close should appear in Monday trading_day aggregate."""
    from backend.app.data.repositories.reddit_daily_feature_repo import RedditDailyFeatureRepository
    from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
    from backend.app.data.repositories.reddit_symbol_mention_repo import RedditSymbolMentionRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.reddit_post import RedditPost
    from backend.app.models.reddit_symbol_mention import RedditSymbolMention
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        post_repo = RedditPostRepository(db)
        mention_repo = RedditSymbolMentionRepository(db)
        feature_repo = RedditDailyFeatureRepository(db)

        stock_repo.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
        db.flush()

        # Friday 2026-02-27 21:30 UTC == 16:30 ET -> effective trading day Monday 2026-03-02
        posted_at = datetime(2026, 2, 27, 21, 30, 0)
        post = RedditPost(
            id="post_fri",
            subreddit="wallstreetbets",
            title="GME after close",
            author="u2",
            upvotes=5,
            comments=1,
            url="https://reddit.com/...",
            posted_at=posted_at,
        )
        post_repo.add(post)
        mention_repo.add(RedditSymbolMention(post_id="post_fri", symbol="GME"))
        db.commit()

        # Aggregate only for Monday; Friday post should still be included via effective_trading_day logic.
        stats = compute_and_store_reddit_daily_features(db, date(2026, 3, 2), date(2026, 3, 2))
        db.commit()
        assert stats["rows_upserted"] == 1
        row = feature_repo.get("GME", date(2026, 3, 2))
        assert row is not None
        assert row.mention_count == 1
        assert row.unique_authors == 1
    finally:
        db.close()

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_daily_feature import RedditDailyFeature
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock
from backend.app.services import status_service as status_service_module


def _build_test_app_with_db() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()
    app = create_app()

    def override_get_session() -> Session:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def test_get_collection_status_counters_and_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """Status endpoint returns expected structure and basic counter/health correctness."""
    client, db = _build_test_app_with_db()

    # Fix \"now\" inside status_service so time windows are deterministic.
    fixed_now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):  # type: ignore[misc]
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_now
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(status_service_module, "datetime", FixedDateTime)

    # Seed minimal data so counters are non-zero and types exercised.
    stock = Stock(symbol="GME", name="GameStop", sector=None, market_cap=None)
    db.add(stock)

    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="GME to the moon",
        author="u1",
        upvotes=10,
        comments=2,
        url="https://reddit.com/...",
        posted_at=fixed_now - timedelta(minutes=30),
        collected_at=fixed_now - timedelta(minutes=30),
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="GME"))

    # Older Reddit post outside 1h window but inside 24h.
    older_post = RedditPost(
        id="post_old",
        subreddit="wallstreetbets",
        title="GME earlier",
        author="u2",
        upvotes=3,
        comments=1,
        url="https://reddit.com/...",
        posted_at=fixed_now - timedelta(hours=2),
        collected_at=fixed_now - timedelta(hours=2),
    )
    db.add(older_post)
    db.add(RedditSymbolMention(post_id="post_old", symbol="GME"))

    price = PriceData(
        stock_symbol="GME",
        date=fixed_now.date(),
        open=10.0,
        high=12.0,
        low=9.5,
        close=11.0,
        volume=1000,
    )
    db.add(price)

    feature = RedditDailyFeature(
        symbol="GME",
        trading_day=fixed_now.date(),
        mention_count=1,
        unique_authors=1,
        total_upvotes=10,
        total_comments=2,
        upvote_weighted_mentions=1.0,
    )
    db.add(feature)
    db.commit()

    resp = client.get("/api/status/collection")
    assert resp.status_code == 200
    body = resp.json()

    assert "server_time_utc" in body
    assert "market_time_local" in body
    assert isinstance(body.get("jobs"), list)

    reddit = body.get("reddit")
    assert isinstance(reddit, dict)
    assert reddit["posts_last_1h"] == 1
    assert reddit["posts_last_24h"] == 2
    assert reddit["mentions_last_1h"] == 1
    assert reddit["mentions_last_24h"] == 2

    prices = body.get("prices")
    assert isinstance(prices, dict)
    assert prices["newest_price_date"].startswith(fixed_now.date().isoformat())
    assert prices["price_rows_last_7d"] == 1
    assert prices["price_rows_last_30d"] == 1

    daily = body.get("daily_features")
    assert isinstance(daily, dict)
    assert daily["newest_trading_day"].startswith(fixed_now.date().isoformat())
    assert daily["rows_last_7d"] == 1
    assert daily["rows_last_30d"] == 1

    health = body.get("health")
    assert isinstance(health, dict)
    assert health["reddit"] in {"ok", "stale", "empty"}
    assert health["prices"] in {"ok", "stale", "empty"}
    assert health["daily_features"] in {"ok", "stale", "empty"}
    assert health["jobs"] in {"ok", "warning"}

from __future__ import annotations

from datetime import date, datetime, timezone

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


def test_get_collection_status_smoke() -> None:
    """Smoke test: /api/status/collection returns expected top-level fields and nested structures."""
    client, db = _build_test_app_with_db()

    # Seed minimal data so counters are non-zero and types exercised.
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)
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
        posted_at=now,
        collected_at=now,
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="GME"))

    price = PriceData(
        stock_symbol="GME",
        date=date(2026, 3, 1),
        open=10.0,
        high=12.0,
        low=9.5,
        close=11.0,
        volume=1000,
    )
    db.add(price)

    feature = RedditDailyFeature(
        symbol="GME",
        trading_day=date(2026, 3, 1),
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
    assert "posts_last_24h" in reddit

    prices = body.get("prices")
    assert isinstance(prices, dict)
    assert "newest_price_date" in prices

    daily = body.get("daily_features")
    assert isinstance(daily, dict)
    assert "newest_trading_day" in daily


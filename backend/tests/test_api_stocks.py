from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock


def create_test_engine_and_sessionmaker():
    # Use a file-based SQLite DB so that connections in different sessions
    # see the same schema and data. This is cleaned up in-memory for tests.
    engine = create_engine("sqlite:///./test_api.db", future=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, TestSessionLocal


def build_test_app_with_db() -> tuple[TestClient, Session]:
    engine, TestSessionLocal = create_test_engine_and_sessionmaker()
    session = TestSessionLocal()
    app = create_app()

    # Override DB dependency to use our in-memory session.
    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session

    return TestClient(app), session


def test_list_and_get_stocks() -> None:
    client, db = build_test_app_with_db()

    # Seed one stock
    stock = Stock(
        symbol="GME", name="GameStop", sector="Retail", market_cap=1_000_000_000
    )
    db.add(stock)
    db.commit()

    resp = client.get("/api/stocks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(s["symbol"] == "GME" for s in data)

    resp2 = client.get("/api/stocks/GME")
    assert resp2.status_code == 200
    detail = resp2.json()
    assert detail["symbol"] == "GME"
    assert detail["name"] == "GameStop"


def test_get_stock_not_found_returns_404() -> None:
    client, _ = build_test_app_with_db()
    resp = client.get("/api/stocks/UNKNOWN")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error_type"] == "NotFoundError"


def test_get_sentiment_and_prices_for_stock() -> None:
    client, db = build_test_app_with_db()

    now = datetime.now(timezone.utc)

    stock = Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None)
    db.add(stock)

    # Seed one reddit post with symbol mention
    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="AMC to the moon buy buy",
        author="user",
        upvotes=100,
        comments=10,
        url="https://reddit.com/post1",
        posted_at=now,
        collected_at=now,
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="post1", symbol="AMC"))

    # Seed one price bar
    price = PriceData(
        stock_symbol="AMC",
        date=date(2024, 1, 1),
        open=10.0,
        high=12.0,
        low=9.5,
        close=11.5,
        volume=1_000_000,
    )
    db.add(price)
    db.commit()

    # Sentiment
    s_resp = client.get("/api/stocks/AMC/sentiment")
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["stock_symbol"] == "AMC"
    assert s_data["mention_count"] == 1
    assert s_data["classification"] in {"positive", "neutral", "negative", "no_data"}

    # Prices
    p_resp = client.get("/api/stocks/AMC/prices")
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert isinstance(p_data, list)
    assert len(p_data) == 1
    assert p_data[0]["close"] == 11.5

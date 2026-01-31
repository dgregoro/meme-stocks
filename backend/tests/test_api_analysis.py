from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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
    engine = create_engine("sqlite:///./test_api_analysis.db", future=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, TestSessionLocal


def build_test_app_with_db() -> tuple[TestClient, Session]:
    engine, TestSessionLocal = create_test_engine_and_sessionmaker()
    session = TestSessionLocal()

    app = create_app()

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session

    return TestClient(app), session


def test_daily_analysis_ranks_stocks_by_composite_score() -> None:
    client, db = build_test_app_with_db()

    now = datetime.now(timezone.utc)

    # Two stocks with different sentiment and trends
    gme = Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None)
    amc = Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None)
    db.add_all([gme, amc])

    # GME: strongly positive post
    gme_post = RedditPost(
        id="gme1",
        subreddit="wallstreetbets",
        title="GME to the moon buy buy",
        author="user",
        upvotes=200,
        comments=20,
        url="https://reddit.com/gme1",
        posted_at=now,
        collected_at=now,
    )
    # AMC: negative/neutral post
    amc_post = RedditPost(
        id="amc1",
        subreddit="wallstreetbets",
        title="AMC is a scam sell",
        author="user",
        upvotes=50,
        comments=5,
        url="https://reddit.com/amc1",
        posted_at=now,
        collected_at=now,
    )
    db.add_all([gme_post, amc_post])
    db.add_all([
        RedditSymbolMention(post_id="gme1", symbol="GME"),
        RedditSymbolMention(post_id="amc1", symbol="AMC"),
    ])

    # GME price trending up, AMC trending down
    for i in range(60):
        db.add(
            PriceData(
                stock_symbol="GME",
                date=date(2024, 1, 1) + timedelta(days=i),
                open=10.0 + i,
                high=11.0 + i,
                low=9.5 + i,
                close=10.5 + i,
                volume=1_000_000,
            )
        )
        db.add(
            PriceData(
                stock_symbol="AMC",
                date=date(2024, 1, 1) + timedelta(days=i),
                open=100.0 - i,
                high=101.0 - i,
                low=99.0 - i,
                close=99.5 - i,
                volume=1_000_000,
            )
        )

    db.commit()

    resp = client.get("/api/analysis/daily")
    assert resp.status_code == 200
    data = resp.json()

    # We expect two entries, with GME ranked above AMC
    assert len(data) == 2
    assert data[0]["symbol"] == "GME"
    assert data[1]["symbol"] == "AMC"
    assert data[0]["composite_score"] >= data[1]["composite_score"]

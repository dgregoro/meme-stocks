from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.reddit_post import RedditPost
from backend.app.services.notification_service import generate_notifications_for_stock


def create_test_engine_and_sessionmaker():
    engine = create_engine("sqlite:///./test_notifications.db", future=True)
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


def seed_stock_with_activity(db: Session) -> str:
    symbol = "GME"
    now = datetime.now(timezone.utc)

    stock = Stock(symbol=symbol, name="GameStop", sector="Retail", market_cap=None)
    db.add(stock)

    # Two price points with strong upward move and volume spike
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 1),
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.0,
            volume=500_000,
        )
    )
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 2),
            open=12.0,
            high=13.0,
            low=11.5,
            close=12.5,
            volume=2_000_000,
        )
    )

    # One strongly positive reddit post
    post = RedditPost(
        id="post1",
        stock_symbol=symbol,
        subreddit="wallstreetbets",
        title="GME moon buy buy",
        author="user",
        upvotes=300,
        comments=30,
        url="https://reddit.com/post1",
        posted_at=now,
        collected_at=now,
    )
    db.add(post)

    db.commit()
    return symbol


def test_generate_notifications_and_list_via_api() -> None:
    client, db = build_test_app_with_db()
    symbol = seed_stock_with_activity(db)

    # Generate notifications using the service
    notifs = generate_notifications_for_stock(db, symbol)
    db.commit()

    assert len(notifs) >= 1

    # Fetch via API
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == len(notifs)
    assert {n["stock_symbol"] for n in data} == {symbol}



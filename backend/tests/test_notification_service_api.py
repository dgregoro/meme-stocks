from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock
from backend.app.services.notification_service import generate_notifications_for_stock


def create_test_engine_and_sessionmaker():
    # Use StaticPool to share the in-memory database across connections
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, TestSessionLocal


def build_test_app_with_db() -> tuple[TestClient, Session]:
    engine, TestSessionLocal = create_test_engine_and_sessionmaker()
    session = TestSessionLocal()

    app = create_app(omit_scheduler=True)

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

    # One strongly positive reddit post with symbol mention
    post = RedditPost(
        id="post1",
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
    db.add(RedditSymbolMention(post_id="post1", symbol=symbol))

    db.commit()
    return symbol


def test_generate_notifications_for_stock_returns_empty_when_stock_missing() -> None:
    """Test that generate_notifications_for_stock returns [] when symbol is not in DB."""
    _, db = build_test_app_with_db()
    result = generate_notifications_for_stock(db, "NONEXISTENT")
    assert result == []


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


def seed_stock_volume_only(db: Session) -> str:
    """Seed with only volume spike (no price move beyond threshold)."""
    symbol = "VOLO"
    stock = Stock(symbol=symbol, name="VolumeOnly", sector="Tech", market_cap=None)
    db.add(stock)
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 1),
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.0,
            volume=100_000,
        )
    )
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 2),
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.05,  # 0.5% move - below 5% threshold
            volume=500_000,  # 5x average - volume spike
        )
    )
    db.commit()
    return symbol


def test_one_signal_no_combined_alert() -> None:
    """One signal only => no combined alert (SC-001)."""
    client, db = build_test_app_with_db()
    symbol = seed_stock_volume_only(db)
    notifs = generate_notifications_for_stock(db, symbol)
    db.commit()
    combined = [n for n in notifs if n.type == "combined_signal"]
    assert len(combined) == 0


def seed_stock_multiple_signals_above_threshold(db: Session) -> str:
    """Seed with volume + price + sentiment to exceed combined threshold."""
    symbol = "MOON"
    now = datetime.now(timezone.utc)
    stock = Stock(symbol=symbol, name="MoonStock", sector="Tech", market_cap=None)
    db.add(stock)
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 1),
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.0,
            volume=200_000,
        )
    )
    db.add(
        PriceData(
            stock_symbol=symbol,
            date=date(2024, 1, 2),
            open=12.0,
            high=13.0,
            low=11.0,
            close=12.5,  # 25% up
            volume=800_000,  # 4x avg
        )
    )
    post = RedditPost(
        id="moon1",
        subreddit="wallstreetbets",
        title="MOON buy buy bullish",
        author="user",
        upvotes=500,
        comments=50,
        url="https://reddit.com/moon1",
        posted_at=now,
        collected_at=now,
    )
    db.add(post)
    db.add(RedditSymbolMention(post_id="moon1", symbol=symbol))
    db.commit()
    return symbol


def test_multiple_signals_above_threshold_creates_combined_alert() -> None:
    """Two+ signals, score >= threshold => combined alert created."""
    client, db = build_test_app_with_db()
    symbol = seed_stock_multiple_signals_above_threshold(db)
    notifs = generate_notifications_for_stock(db, symbol)
    db.commit()
    combined = [n for n in notifs if n.type == "combined_signal"]
    assert len(combined) >= 1
    assert combined[0].signal_metadata is not None


def test_combined_signal_alerts_only_false_coexist() -> None:
    """combined_signal_alerts_only=False => individual + combined coexist."""
    client, db = build_test_app_with_db()
    symbol = seed_stock_multiple_signals_above_threshold(db)
    with patch("backend.app.services.notification_service.get_settings") as mock:
        mock.return_value.combined_signal_alerts_only = False
        mock.return_value.combined_signal_weight_sentiment = 2.0
        mock.return_value.combined_signal_weight_price = 2.0
        mock.return_value.combined_signal_weight_volume = 1.0
        mock.return_value.combined_signal_weight_rsi = 1.0
        mock.return_value.combined_signal_threshold = 4.0
        mock.return_value.sentiment_window_hours = 24
        notifs = generate_notifications_for_stock(db, symbol)
    db.commit()
    combined = [n for n in notifs if n.type == "combined_signal"]
    individual = [n for n in notifs if n.type != "combined_signal"]
    assert len(combined) >= 1
    assert len(individual) >= 1


def test_combined_signal_alerts_only_true_suppress_individual() -> None:
    """combined_signal_alerts_only=True => only combined, no individual."""
    client, db = build_test_app_with_db()
    symbol = seed_stock_multiple_signals_above_threshold(db)
    with patch("backend.app.services.notification_service.get_settings") as mock:
        mock.return_value.combined_signal_alerts_only = True
        mock.return_value.combined_signal_weight_sentiment = 2.0
        mock.return_value.combined_signal_weight_price = 2.0
        mock.return_value.combined_signal_weight_volume = 1.0
        mock.return_value.combined_signal_weight_rsi = 1.0
        mock.return_value.combined_signal_threshold = 4.0
        mock.return_value.sentiment_window_hours = 24
        notifs = generate_notifications_for_stock(db, symbol)
    db.commit()
    combined = [n for n in notifs if n.type == "combined_signal"]
    individual = [n for n in notifs if n.type != "combined_signal"]
    assert len(combined) >= 1
    assert len(individual) == 0


def test_notification_api_returns_signal_metadata_for_combined_type() -> None:
    """GET /api/notifications returns signal_metadata for combined_signal; shape matches contract."""
    client, db = build_test_app_with_db()
    symbol = seed_stock_multiple_signals_above_threshold(db)
    generate_notifications_for_stock(db, symbol)
    db.commit()

    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    combined = [n for n in data if n.get("type") == "combined_signal"]
    assert len(combined) >= 1

    meta = combined[0].get("signal_metadata")
    assert meta is not None
    assert "evaluation_timestamp" in meta
    assert "combined_score" in meta
    assert "threshold" in meta
    assert "signals_evaluated" in meta

    for s in meta["signals_evaluated"]:
        assert "signal_type" in s
        assert "fired" in s
        assert "contribution" in s

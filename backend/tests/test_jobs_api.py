from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.data.database import Base, SessionLocal, engine
from backend.app.main import create_app
from backend.app.services.scheduler_service import SchedulerService


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def test_app():
    """Create a test FastAPI app with TestClient for lifespan support."""
    Base.metadata.create_all(engine)

    mock_scheduler = MagicMock(spec=SchedulerService)
    app = create_app(scheduler_for_testing=mock_scheduler)
    with TestClient(app) as client:
        yield app, mock_scheduler, client

    Base.metadata.drop_all(engine)


def test_trigger_reddit_collection(test_app):
    """Test manual Reddit collection endpoint."""
    app, mock_scheduler, client = test_app

    # Mock the collection method to return stats
    mock_scheduler._collect_reddit_data = MagicMock(
        return_value={
            "posts_fetched": 10,
            "posts_with_tickers": 5,
            "posts_saved": 3,
        }
    )

    response = client.post("/api/jobs/reddit-collection")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "reddit_collection"
    assert data["status"] == "success"
    assert data["stats"] == {
        "posts_fetched": 10,
        "posts_with_tickers": 5,
        "posts_saved": 3,
    }
    mock_scheduler._collect_reddit_data.assert_called_once()


def test_trigger_price_collection(test_app):
    """Test manual price collection endpoint."""
    app, mock_scheduler, client = test_app

    mock_scheduler._collect_price_data = MagicMock()

    response = client.post("/api/jobs/price-collection")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "price_collection"
    assert data["status"] == "success"
    mock_scheduler._collect_price_data.assert_called_once()


def test_trigger_notification_check(test_app):
    """Test manual notification check endpoint."""
    app, mock_scheduler, client = test_app

    mock_scheduler._check_notifications = MagicMock()

    response = client.post("/api/jobs/notification-check")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "notification_check"
    assert data["status"] == "success"
    mock_scheduler._check_notifications.assert_called_once()


def test_job_endpoint_without_scheduler():
    """Test that endpoints return 503 if scheduler not initialized."""
    app = create_app(omit_scheduler=True)

    with TestClient(app) as client:
        response = client.post("/api/jobs/reddit-collection")

    assert response.status_code == 503
    assert "Scheduler not initialized" in response.json()["detail"]


def test_get_recent_reddit_posts_empty(db_session):
    """Test getting recent Reddit posts when none exist."""
    app = create_app()
    client = TestClient(app)
    
    response = client.get("/api/jobs/reddit-collection/recent")
    
    assert response.status_code == 200
    assert response.json() == []


def test_get_recent_reddit_posts_with_data(db_session):
    """Test getting recent Reddit posts when some exist."""
    from datetime import datetime, timezone

    from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
    from backend.app.data.repositories.reddit_symbol_mention_repo import (
        RedditSymbolMentionRepository,
    )
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.reddit_post import RedditPost
    from backend.app.models.reddit_symbol_mention import RedditSymbolMention
    from backend.app.models.stock import Stock

    # Create a stock first
    stock_repo = StockRepository(db_session)
    stock = Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None)
    stock_repo.add(stock)
    db_session.commit()

    # Create Reddit posts with symbol mentions
    now = datetime.now(timezone.utc)
    post_repo = RedditPostRepository(db_session)
    mention_repo = RedditSymbolMentionRepository(db_session)
    for i in range(3):
        post = RedditPost(
            id=f"post{i}",
            subreddit="wallstreetbets",
            title=f"GME post {i}",
            author=f"user{i}",
            upvotes=100 + i,
            comments=50 + i,
            url=f"https://reddit.com/post{i}",
            posted_at=now,
            collected_at=now,
        )
        post_repo.add(post)
        mention_repo.add(RedditSymbolMention(post_id=f"post{i}", symbol="GME"))
    db_session.commit()

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/jobs/reddit-collection/recent?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("id" in post for post in data)
    assert all("stock_symbol" in post for post in data)
    assert all("title" in post for post in data)
    assert data[0]["stock_symbol"] == "GME"


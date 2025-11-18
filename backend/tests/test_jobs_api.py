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
    """Create a test FastAPI app."""
    # Ensure tables are created
    Base.metadata.create_all(engine)
    
    app = create_app()
    # Mock scheduler for testing
    mock_scheduler = MagicMock(spec=SchedulerService)
    from backend.app.api import jobs as jobs_api

    jobs_api.set_scheduler(mock_scheduler)
    yield app, mock_scheduler
    
    # Cleanup
    Base.metadata.drop_all(engine)


def test_trigger_reddit_collection(test_app):
    """Test manual Reddit collection endpoint."""
    app, mock_scheduler = test_app

    # Mock the collection method to return stats
    mock_scheduler._collect_reddit_data = MagicMock(
        return_value={
            "posts_fetched": 10,
            "posts_with_tickers": 5,
            "posts_saved": 3,
        }
    )

    client = TestClient(app)
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
    app, mock_scheduler = test_app

    mock_scheduler._collect_price_data = MagicMock()

    client = TestClient(app)
    response = client.post("/api/jobs/price-collection")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "price_collection"
    assert data["status"] == "success"
    mock_scheduler._collect_price_data.assert_called_once()


def test_trigger_notification_check(test_app):
    """Test manual notification check endpoint."""
    app, mock_scheduler = test_app

    mock_scheduler._check_notifications = MagicMock()

    client = TestClient(app)
    response = client.post("/api/jobs/notification-check")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "notification_check"
    assert data["status"] == "success"
    mock_scheduler._check_notifications.assert_called_once()


def test_job_endpoint_without_scheduler():
    """Test that endpoints return 503 if scheduler not initialized."""
    app = create_app()
    # Don't set scheduler
    from backend.app.api import jobs as jobs_api

    jobs_api.set_scheduler(None)

    client = TestClient(app)
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
    from backend.app.models.reddit_post import RedditPost
    from backend.app.models.stock import Stock
    from backend.app.data.repositories.stock_repo import StockRepository
    
    # Create a stock first
    stock_repo = StockRepository(db_session)
    stock = Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None)
    stock_repo.add(stock)
    db_session.commit()
    
    # Create some Reddit posts
    now = datetime.now(timezone.utc)
    posts = [
        RedditPost(
            id=f"post{i}",
            stock_symbol="GME",
            subreddit="wallstreetbets",
            title=f"GME post {i}",
            author=f"user{i}",
            upvotes=100 + i,
            comments=50 + i,
            url=f"https://reddit.com/post{i}",
            posted_at=now,
            collected_at=now,
        )
        for i in range(3)
    ]
    
    for post in posts:
        db_session.add(post)
    db_session.commit()
    
    app = create_app()
    client = TestClient(app)
    
    response = client.get("/api/jobs/reddit-collection/recent?limit=5")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("id" in post for post in data)
    assert all("stock_symbol" in post for post in data)
    assert all("title" in post for post in data)
    assert data[0]["stock_symbol"] == "GME"


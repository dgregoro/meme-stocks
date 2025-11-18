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


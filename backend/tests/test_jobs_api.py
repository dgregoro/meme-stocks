from __future__ import annotations

from unittest.mock import MagicMock

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


def test_trigger_price_collection(test_app):
    """Test manual price collection endpoint."""
    app, mock_scheduler, client = test_app

    mock_scheduler._collect_price_data = MagicMock(return_value={"rows_inserted": 1, "symbols": 1})

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


def test_trigger_leader_follower_detection(test_app):
    """Test manual leader-follower detection endpoint."""
    app, mock_scheduler, client = test_app

    mock_scheduler._leader_follower_detection_job = MagicMock()

    response = client.post("/api/jobs/leader-follower-detection")

    assert response.status_code == 200
    data = response.json()
    assert data["job_name"] == "leader_follower_detection"
    assert data["status"] == "success"
    mock_scheduler._leader_follower_detection_job.assert_called_once()


def test_job_endpoint_without_scheduler():
    """Test that endpoints return 503 if scheduler not initialized."""
    app = create_app(omit_scheduler=True)

    with TestClient(app) as client:
        response = client.post("/api/jobs/price-collection")

    assert response.status_code == 503
    assert "Scheduler not initialized" in response.json()["detail"]["message"]


def test_get_job_runs_empty(db_session):
    """Test GET job runs when none exist."""
    app = create_app(omit_scheduler=True)
    with TestClient(app) as client:
        response = client.get("/api/jobs/price-collection/runs")

    assert response.status_code == 200
    assert response.json() == []


def test_get_job_runs_with_data(db_session):
    """Test GET job runs returns last 30 runs for a job."""
    from datetime import datetime, timezone

    from backend.app.data.repositories.job_execution_repo import JobExecutionRepository

    repo = JobExecutionRepository(db_session)
    now = datetime.now(timezone.utc)
    for _ in range(5):
        repo.record_run("price_collection", run_at=now)
    db_session.commit()

    app = create_app(omit_scheduler=True)
    with TestClient(app) as client:
        response = client.get("/api/jobs/price-collection/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert all(r["job_name"] == "price_collection" for r in data)
    assert all("run_at" in r and "id" in r for r in data)


def test_get_job_runs_unknown_job_returns_404(db_session):
    """Test GET job runs for unknown job returns 404."""
    app = create_app(omit_scheduler=True)
    with TestClient(app) as client:
        response = client.get("/api/jobs/nonexistent/runs")

    assert response.status_code == 404

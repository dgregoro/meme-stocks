from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.data.repositories.job_execution_repo import JobExecutionRepository
from backend.app.main import create_app


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


def test_job_endpoint_without_scheduler(isolated_sqlite_engine):
    """Endpoints return 503 if scheduler not initialized (isolated DB for lifespan)."""
    from sqlalchemy.orm import sessionmaker

    MainSession = sessionmaker(
        bind=isolated_sqlite_engine,
        autocommit=False,
        autoflush=False,
    )
    with patch("backend.app.main.init_db"), patch("backend.app.main.SessionLocal", MainSession):
        app = create_app(omit_scheduler=True)

        with TestClient(app) as client:
            response = client.post("/api/jobs/price-collection")

    assert response.status_code == 503
    assert "Scheduler not initialized" in response.json()["detail"]["message"]


def test_get_job_runs_empty(isolated_omit_scheduler_client):
    """Test GET job runs when none exist."""
    client, _MainSession = isolated_omit_scheduler_client
    response = client.get("/api/jobs/price-collection/runs")

    assert response.status_code == 200
    assert response.json() == []


def test_get_job_runs_with_data(isolated_omit_scheduler_client):
    """Test GET job runs returns last 30 runs for a job."""
    from datetime import datetime, timezone

    client, MainSession = isolated_omit_scheduler_client
    db = MainSession()
    try:
        repo = JobExecutionRepository(db)
        now = datetime.now(timezone.utc)
        for _ in range(5):
            repo.record_run("price_collection", run_at=now)
        db.commit()
    finally:
        db.close()

    response = client.get("/api/jobs/price-collection/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert all(r["job_name"] == "price_collection" for r in data)
    assert all("run_at" in r and "id" in r for r in data)


def test_get_job_runs_unknown_job_returns_404(isolated_omit_scheduler_client):
    """Test GET job runs for unknown job returns 404."""
    client, _MainSession = isolated_omit_scheduler_client
    response = client.get("/api/jobs/nonexistent/runs")

    assert response.status_code == 404

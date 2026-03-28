"""Tests for Alpaca free-plan safety window (delay buffer)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.clients.alpaca_data_client import (
    AlpacaDataClient,
    compute_safe_end_time,
)
from backend.app.main import create_app
from backend.app.services.intraday_ingestion_service import run_intraday_ingestion


@pytest.mark.unit
def test_compute_safe_end_time_free_plan_mode_true() -> None:
    """When alpaca_free_plan_mode=True and safety=20, safe_end_time is now - 20 min."""
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = compute_safe_end_time(now, safety_minutes=20, free_plan_mode=True)
    assert end == datetime(2026, 3, 1, 11, 40, 0, tzinfo=timezone.utc)


@pytest.mark.unit
def test_compute_safe_end_time_free_plan_mode_false() -> None:
    """When free_plan_mode=False, end equals now (no buffer)."""
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = compute_safe_end_time(now, safety_minutes=20, free_plan_mode=False)
    assert end == now


@pytest.mark.unit
def test_edge_case_end_before_12_40() -> None:
    """If now is 2026-03-01T12:00Z, ensure end <= 11:40Z."""
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = compute_safe_end_time(now, safety_minutes=20, free_plan_mode=True)
    assert end <= datetime(2026, 3, 1, 11, 40, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 1, 11, 40, 0, tzinfo=timezone.utc)


@pytest.mark.unit
def test_ingestion_service_uses_safe_end_time() -> None:
    """Ingestion service uses compute_safe_end_time when building request params."""
    from datetime import datetime as real_dt, timedelta, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app.data.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        with patch("backend.app.services.intraday_ingestion_service.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.alpaca_free_plan_mode = True
            mock_settings.alpaca_end_time_safety_minutes = 20
            mock_settings.alpaca_data_feed = "delayed_sip"
            mock_settings.alpaca_bars_feed = "iex"
            mock_settings.intraday_universe_mode = "tracked"
            mock_settings.intraday_feature_store_root = "/tmp/test_intraday_store"
            mock_settings.intraday_symbols_batch_size = 200
            mock_settings.intraday_lookback_days = 30
            mock_settings.intraday_max_pages_per_batch = 100
            mock_get_settings.return_value = mock_settings

        with patch("backend.app.services.intraday_ingestion_service.datetime") as mock_dt:
            mock_dt.now.return_value = real_dt(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.timedelta = timedelta
            mock_dt.timezone = timezone
            fixed_end = real_dt(2026, 3, 1, 11, 40, 0, tzinfo=timezone.utc)
            with patch("backend.app.clients.alpaca_data_client.requests.get") as mock_req:
                mock_req.return_value.status_code = 200
                mock_req.return_value.json.return_value = {"bars": {}, "next_page_token": None}
                result = run_intraday_ingestion(db, universe=["AAPL"])

            assert result["bars_written"] == 0
            assert result["symbols_processed"] == 1
            assert result["safe_end_used"] == fixed_end.isoformat()
            assert mock_req.called
            if mock_req.called:
                call_params = mock_req.call_args[1]["params"]
                assert call_params["feed"] == "iex"
                assert "start" in call_params
                assert "end" in call_params
    finally:
        db.close()


@pytest.mark.unit
def test_alpaca_client_compute_safe_end_time_delegates() -> None:
    """AlpacaDataClient.compute_safe_end_time uses module helper with instance config."""
    client = AlpacaDataClient(
        free_plan_mode=True,
        end_time_safety_minutes=20,
        feed="iex",
    )
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = client.compute_safe_end_time(now)
    assert end == datetime(2026, 3, 1, 11, 40, 0, tzinfo=timezone.utc)


@pytest.mark.unit
def test_intraday_status_reports_lag_and_safety() -> None:
    """GET /api/intraday/status returns alpaca_feed, free_plan_mode, safety, notes, and progress fields."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.app.data.database import Base, get_session

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_session():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app(omit_scheduler=True)
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    response = client.get("/api/intraday/status")
    assert response.status_code == 200
    data = response.json()
    assert data["alpaca_feed"] == "iex"  # default alpaca_bars_feed for historical bars
    assert data["free_plan_mode"] is True
    assert data["sip_delay_minutes"] == 15
    assert data["end_time_safety_minutes"] == 20
    assert data["effective_data_lag_minutes"] == 20
    assert "Historical bars feed=iex" in data["notes"]
    assert "20 minutes" in data["notes"]
    assert "counts_by_status" in data
    assert "newest_last_ts" in data
    assert "oldest_last_ts" in data
    assert "latest_run" in data
    assert "intraday_ingestion_enabled" in data


@pytest.mark.integration
def test_intraday_status_with_lock_held_returns_200_and_lock_info() -> None:
    """GET /api/intraday/status returns 200 with lock.held=True when JobLock exists and is not expired."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.app.data.database import Base, get_session
    from backend.app.data.repositories.job_lock_repo import JobLockRepository
    from backend.app.models import job_lock  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    # Acquire lock so status endpoint sees it (may have naive expires_at from SQLite)
    db = TestSession()
    lock_repo = JobLockRepository(db)
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    lock_repo.try_acquire_lock("intraday_ingestion", "scheduler", ttl_seconds=86400 * 365, now=now)
    db.commit()
    db.close()

    def override_get_session():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app(omit_scheduler=True)
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    response = client.get("/api/intraday/status")
    assert response.status_code == 200
    data = response.json()
    assert data["lock"]["enabled"] is True
    assert data["lock"]["held"] is True
    assert data["lock"]["owner"] == "scheduler"
    assert "expires_at" in data["lock"]

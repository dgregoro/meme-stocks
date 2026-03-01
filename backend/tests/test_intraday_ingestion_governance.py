"""Tests for intraday ingestion governance: lock prevents concurrent runs."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import job_lock  # noqa: F401
from backend.app.data.repositories.job_lock_repo import JobLockRepository
from backend.app.services.intraday_ingestion_service import run_intraday_ingestion
from backend.app.utils.errors import IngestionAlreadyRunningError


@pytest.mark.integration
def test_run_intraday_ingestion_raises_when_lock_held() -> None:
    """When lock is held by another owner, run_intraday_ingestion raises IngestionAlreadyRunningError."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        lock_repo = JobLockRepository(db)
        # Use a lock that expires in the future so the service sees it as held
        now = datetime.now(timezone.utc) - timedelta(seconds=10)
        lock_repo.try_acquire_lock("intraday_ingestion", "scheduler", ttl_seconds=3600, now=now)
        db.commit()

        with patch("backend.app.services.intraday_ingestion_service.get_settings") as mock_settings:
            mock_settings.return_value.intraday_lock_enabled = True
            mock_settings.return_value.intraday_lock_name = "intraday_ingestion"
            mock_settings.return_value.intraday_lock_ttl_seconds = 1800
            mock_settings.return_value.alpaca_free_plan_mode = True
            mock_settings.return_value.alpaca_end_time_safety_minutes = 20
            mock_settings.return_value.alpaca_data_feed = "delayed_sip"
            mock_settings.return_value.alpaca_api_key_id = None
            mock_settings.return_value.alpaca_api_secret_key = None
            mock_settings.return_value.alpaca_data_base_url = "https://data.alpaca.markets"
            mock_settings.return_value.intraday_universe_mode = "tracked"
            mock_settings.return_value.intraday_feature_store_root = "/tmp/test_governance"
            mock_settings.return_value.intraday_symbols_batch_size = 2
            mock_settings.return_value.intraday_lookback_days = 1
            mock_settings.return_value.intraday_max_pages_per_batch = 10

            with pytest.raises(IngestionAlreadyRunningError) as exc_info:
                run_intraday_ingestion(db, universe=["AAPL"], owner="api:test-uuid")

            assert "already in progress" in str(exc_info.value).lower() or "already in progress" in (
                exc_info.value.args[0] or ""
            )
            assert exc_info.value.owner == "scheduler"
    finally:
        db.close()


@pytest.mark.integration
def test_run_intraday_ingestion_raises_when_lock_disabled_and_run_in_progress() -> None:
    """When lock is disabled but a run is in progress, service raises (no silent skip)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        with patch("backend.app.services.intraday_ingestion_service.get_settings") as mock_settings:
            mock_settings.return_value.intraday_lock_enabled = False
            mock_settings.return_value.alpaca_free_plan_mode = True
            mock_settings.return_value.alpaca_end_time_safety_minutes = 20
            mock_settings.return_value.alpaca_data_feed = "delayed_sip"
            mock_settings.return_value.alpaca_api_key_id = None
            mock_settings.return_value.alpaca_api_secret_key = None
            mock_settings.return_value.alpaca_data_base_url = "https://data.alpaca.markets"
            mock_settings.return_value.intraday_universe_mode = "tracked"
            mock_settings.return_value.intraday_feature_store_root = "/tmp/test_governance"
            mock_settings.return_value.intraday_symbols_batch_size = 2
            mock_settings.return_value.intraday_lookback_days = 1
            mock_settings.return_value.intraday_max_pages_per_batch = 10
            with patch("backend.app.services.intraday_ingestion_service.IntradayIngestRepository") as MockRepo:
                mock_repo = MagicMock()
                mock_repo.get_running_run.return_value = MagicMock(id=42)
                MockRepo.return_value = mock_repo

                with pytest.raises(IngestionAlreadyRunningError) as exc_info:
                    run_intraday_ingestion(db, universe=["AAPL"], owner="api:test")

                assert "already in progress" in str(exc_info.value).lower()
                assert exc_info.value.owner == "run_id:42"
    finally:
        db.close()

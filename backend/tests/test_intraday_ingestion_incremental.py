"""Tests for incremental intraday ingestion (last_ts advances, second run fetches deltas)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.intraday_ingest_repo import IntradayIngestRepository
from backend.app.models import intraday_ingest_run, intraday_ingest_state  # noqa: F401
from backend.app.services.intraday_ingestion_service import run_intraday_ingestion


@pytest.mark.unit
def test_intraday_ingestion_incremental_last_ts_advances() -> None:
    """Mock client returns bars in two runs; assert last_ts advances and second run requests start after last_ts."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        with patch("backend.app.services.intraday_ingestion_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                alpaca_free_plan_mode=True,
                alpaca_end_time_safety_minutes=20,
                alpaca_data_feed="delayed_sip",
                intraday_universe_mode="tracked",
                intraday_feature_store_root="/tmp/test_intraday_inc",
                intraday_symbols_batch_size=200,
                intraday_lookback_days=30,
                intraday_max_pages_per_batch=100,
                alpaca_api_key_id=None,
                alpaca_api_secret_key=None,
                alpaca_data_base_url="https://data.alpaca.markets",
            )

        first_bars = {
            "AAPL": [
                {
                    "t": "2026-03-01T09:30:00Z",
                    "o": 100.0,
                    "h": 101.0,
                    "l": 99.0,
                    "c": 100.5,
                    "v": 1000,
                    "n": 10,
                    "vw": 100.2,
                },
                {
                    "t": "2026-03-01T09:31:00Z",
                    "o": 100.5,
                    "h": 101.5,
                    "l": 100.0,
                    "c": 101.0,
                    "v": 1100,
                    "n": 12,
                    "vw": 100.8,
                },
            ],
        }
        second_bars = {
            "AAPL": [
                {
                    "t": "2026-03-01T09:32:00Z",
                    "o": 101.0,
                    "h": 102.0,
                    "l": 100.5,
                    "c": 101.5,
                    "v": 1200,
                    "n": 15,
                    "vw": 101.2,
                },
            ],
        }

        with patch("backend.app.services.intraday_ingestion_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
            with patch("backend.app.clients.alpaca_data_client.requests.get") as mock_req:
                mock_req.return_value.status_code = 200
                mock_req.return_value.json.side_effect = [
                    {"bars": first_bars, "next_page_token": None},
                    {"bars": second_bars, "next_page_token": None},
                ]
                run_intraday_ingestion(db, universe=["AAPL"])
                run_intraday_ingestion(db, universe=["AAPL"])

        assert mock_req.call_count >= 2
        # Second request should have start after first bar range (incremental)
        params1 = mock_req.call_args_list[0][1]["params"]
        params2 = mock_req.call_args_list[1][1]["params"]
        start1 = datetime.fromisoformat(params1["start"].replace("Z", "+00:00"))
        start2 = datetime.fromisoformat(params2["start"].replace("Z", "+00:00"))
        assert start2 >= start1
        repo = IntradayIngestRepository(db)
        states = repo.get_states(["AAPL"])
        assert "AAPL" in states
        assert states["AAPL"].last_ts is not None
        last_ts = states["AAPL"].last_ts
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        assert last_ts.hour == 9 and last_ts.minute == 32
    finally:
        db.close()

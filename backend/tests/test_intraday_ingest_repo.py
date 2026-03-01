"""Smoke tests for intraday ingest repository."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.intraday_ingest_repo import IntradayIngestRepository


@pytest.mark.unit
def test_intraday_ingest_repo_ensure_get_update_smoke() -> None:
    """Smoke test: ensure_symbols, get_states, update_success, mark_error, count_by_status."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        repo = IntradayIngestRepository(db)
        repo.ensure_symbols(["AAPL", "GOOG"])
        db.commit()

        states = repo.get_states(["AAPL", "GOOG", "MSFT"])
        assert len(states) == 2
        assert "AAPL" in states
        assert "GOOG" in states
        assert states["AAPL"].last_ts is None
        assert states["AAPL"].status == "active"

        ts = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        repo.update_success("AAPL", ts)
        db.commit()

        states2 = repo.get_states(["AAPL"])
        assert states2["AAPL"].last_ts is not None
        got = states2["AAPL"].last_ts
        if got.tzinfo is None:
            got = got.replace(tzinfo=timezone.utc)
        assert got == ts

        repo.mark_error("GOOG", "rate limited")
        db.commit()
        states3 = repo.get_states(["GOOG"])
        assert states3["GOOG"].status == "error"
        assert states3["GOOG"].error_count == 1

        counts = repo.count_by_status()
        assert "active" in counts or "error" in counts
        newest = repo.get_newest_last_ts()
        assert newest is not None
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        assert newest == ts
    finally:
        db.close()

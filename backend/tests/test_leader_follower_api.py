"""Tests for leader-follower API."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.leader_event import LeaderEvent
from backend.app.models.leader_follower_candidate import LeaderFollowerCandidate
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.models.stock import Stock


def _create_test_app() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
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


@pytest.mark.unit
def test_leader_follower_api_list_signals() -> None:
    """GET /api/leader-follower/signals returns list; query params limit, since_date, leader, group work."""
    client, db = _create_test_app()

    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    db.commit()

    signal = LeaderFollowerSignal(
        leader_symbol="GME",
        follower_symbol="AMC",
        group_id="meme",
        signal_date=date(2026, 3, 18),
        strength_score=0.72,
        leader_return_pct=8.5,
        leader_volume_ratio=2.1,
    )
    db.add(signal)
    db.commit()

    resp = client.get("/api/leader-follower/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert len(data["signals"]) == 1
    s = data["signals"][0]
    assert s["leader_symbol"] == "GME"
    assert s["follower_symbol"] == "AMC"
    assert s["group_id"] == "meme"
    assert s["strength_score"] == 0.72
    assert s["leader_return_pct"] == 8.5

    resp2 = client.get("/api/leader-follower/signals?limit=10")
    assert resp2.status_code == 200
    assert len(resp2.json()["signals"]) == 1

    resp3 = client.get("/api/leader-follower/signals?leader=GME")
    assert resp3.status_code == 200
    assert len(resp3.json()["signals"]) == 1

    resp4 = client.get("/api/leader-follower/signals?leader=XXX")
    assert resp4.status_code == 200
    assert len(resp4.json()["signals"]) == 0

    resp5 = client.get("/api/leader-follower/signals?group=meme")
    assert resp5.status_code == 200
    assert len(resp5.json()["signals"]) == 1

    resp6 = client.get("/api/leader-follower/signals?since_date=2026-03-17")
    assert resp6.status_code == 200
    assert len(resp6.json()["signals"]) == 1


@pytest.mark.integration
def test_status_no_run_returns_no_run() -> None:
    """GET /api/leader-follower/status returns empty_reason no_run when job never ran."""
    client, _db = _create_test_app()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_run"] is None
    assert data["stage_counts"] is None
    assert data["empty_reason"] == "no_run"


@pytest.mark.integration
def test_status_failed_run_returns_failed() -> None:
    """GET /api/leader-follower/status returns empty_reason failed when last run failed."""
    client, db = _create_test_app()
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            success=False,
            error_message="price fetch failed",
            summary="failed",
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_run"] is not None
    assert data["last_run"]["success"] is False
    assert data["last_run"]["error_message"] == "price fetch failed"
    assert data["empty_reason"] == "failed"


@pytest.mark.integration
def test_status_successful_zero_signals_returns_stage_reason() -> None:
    """GET /api/leader-follower/status returns no_leaders when metrics show zero leaders."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 25,
        "leader_events_detected": 0,
        "follower_candidates_found": 0,
        "signals_emitted": 0,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=2.5,
            success=True,
            error_message=None,
            summary="leader-follower: 0 leaders, 0 signals",
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_run"] is not None
    assert data["stage_counts"]["leader_events_detected"] == 0
    assert data["empty_reason"] == "no_leaders"


@pytest.mark.integration
def test_status_successful_with_signals_returns_ok() -> None:
    """GET /api/leader-follower/status returns empty_reason ok when signals emitted."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 25,
        "leader_events_detected": 3,
        "follower_candidates_found": 12,
        "signals_emitted": 5,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=2.5,
            success=True,
            error_message=None,
            summary="leader-follower: 3 leaders, 5 signals",
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_run"] is not None
    assert data["stage_counts"]["signals_emitted"] == 5
    assert data["empty_reason"] == "ok"


@pytest.mark.integration
def test_runs_empty_returns_empty_list() -> None:
    """GET /api/leader-follower/runs returns runs=[] when no runs."""
    client, _db = _create_test_app()
    resp = client.get("/api/leader-follower/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["runs"] == []


@pytest.mark.integration
def test_runs_with_data_returns_parsed_metrics() -> None:
    """GET /api/leader-follower/runs returns runs with parsed metrics."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 25,
        "leader_events_detected": 3,
        "follower_candidates_found": 12,
        "signals_emitted": 5,
        "symbols_skipped": 0,
        "errors_count": 0,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=2.5,
            success=True,
            error_message=None,
            summary="leader-follower: 3 leaders, 5 signals",
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["id"] >= 1
    assert "2026-03-21" in run["run_at"]
    assert run["success"] is True
    assert run["metrics"]["leader_events_detected"] == 3
    assert run["metrics"]["signals_emitted"] == 5


@pytest.mark.integration
def test_leader_events_returns_events_with_filters() -> None:
    """GET /api/leader-follower/leader-events returns events; filters work."""
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    db.commit()

    db.add(
        LeaderEvent(
            leader_symbol="GME",
            event_date=date(2026, 3, 21),
            return_pct=8.5,
            volume_ratio=2.1,
            direction="up",
            job_run_id=42,
        )
    )
    db.add(
        LeaderEvent(
            leader_symbol="AMC",
            event_date=date(2026, 3, 20),
            return_pct=-5.0,
            volume_ratio=1.5,
            direction="down",
            job_run_id=None,
        )
    )
    db.commit()

    resp = client.get("/api/leader-follower/leader-events")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 2
    gme = next(e for e in data["events"] if e["leader_symbol"] == "GME")
    assert gme["return_pct"] == 8.5
    assert gme["run_id"] == 42

    resp2 = client.get("/api/leader-follower/leader-events?leader=GME")
    assert resp2.status_code == 200
    assert len(resp2.json()["events"]) == 1
    assert resp2.json()["events"][0]["leader_symbol"] == "GME"

    resp3 = client.get("/api/leader-follower/leader-events?run_id=42")
    assert resp3.status_code == 200
    assert len(resp3.json()["events"]) == 1
    assert resp3.json()["events"][0]["run_id"] == 42


@pytest.mark.integration
def test_follower_candidates_returns_candidates_with_filters() -> None:
    """GET /api/leader-follower/follower-candidates returns candidates; filters work."""
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    db.add(Stock(symbol="BB", name="BlackBerry", sector="Tech", market_cap=None))
    db.commit()

    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
    )
    db.add(run)
    db.flush()

    db.add(
        LeaderFollowerCandidate(
            job_run_id=run.id,
            event_date=date(2026, 3, 21),
            leader_symbol="GME",
            follower_symbol="AMC",
            group_id="meme",
        )
    )
    db.add(
        LeaderFollowerCandidate(
            job_run_id=run.id,
            event_date=date(2026, 3, 21),
            leader_symbol="GME",
            follower_symbol="BB",
            group_id="meme",
        )
    )
    db.add(
        LeaderFollowerCandidate(
            job_run_id=run.id,
            event_date=date(2026, 3, 20),
            leader_symbol="AMC",
            follower_symbol="GME",
            group_id="meme",
        )
    )
    db.commit()

    resp = client.get("/api/leader-follower/follower-candidates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 3

    resp2 = client.get("/api/leader-follower/follower-candidates?leader=GME")
    assert resp2.status_code == 200
    assert len(resp2.json()["candidates"]) == 2
    assert all(c["leader_symbol"] == "GME" for c in resp2.json()["candidates"])

    resp3 = client.get("/api/leader-follower/follower-candidates?follower=AMC")
    assert resp3.status_code == 200
    assert len(resp3.json()["candidates"]) == 1
    assert resp3.json()["candidates"][0]["follower_symbol"] == "AMC"

    resp4 = client.get("/api/leader-follower/follower-candidates?run_id=%d" % run.id)
    assert resp4.status_code == 200
    assert len(resp4.json()["candidates"]) == 3

    resp5 = client.get("/api/leader-follower/follower-candidates?since_date=2026-03-21")
    assert resp5.status_code == 200
    assert len(resp5.json()["candidates"]) == 2


@pytest.mark.integration
def test_signals_empty_returns_diagnostics() -> None:
    """GET /api/leader-follower/signals with no signals returns diagnostics block."""
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.commit()

    # No signals in DB; no run → diagnostics with no_run
    resp = client.get("/api/leader-follower/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["signals"] == []
    assert "diagnostics" in data
    diag = data["diagnostics"]
    assert diag["last_run_id"] is None
    assert diag["last_run_at"] is None
    assert diag["stage_counts"] is None
    assert diag["empty_reason"] == "no_run"

    # Add a run with no_leaders metrics; still no signals → diagnostics with run info
    metrics = {
        "input_universe_size": 25,
        "leader_events_detected": 0,
        "follower_candidates_found": 0,
        "signals_emitted": 0,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=2.5,
            success=True,
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()

    resp2 = client.get("/api/leader-follower/signals")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["signals"] == []
    assert "diagnostics" in data2
    diag2 = data2["diagnostics"]
    assert diag2["last_run_id"] is not None
    assert "2026-03-21" in (diag2["last_run_at"] or "")
    assert diag2["stage_counts"]["leader_events_detected"] == 0
    assert diag2["empty_reason"] == "no_leaders"


@pytest.mark.integration
def test_signals_with_results_omits_diagnostics() -> None:
    """GET /api/leader-follower/signals with signals returns no diagnostics."""
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    db.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    db.commit()

    db.add(
        LeaderFollowerSignal(
            leader_symbol="GME",
            follower_symbol="AMC",
            group_id="meme",
            signal_date=date(2026, 3, 18),
            strength_score=0.72,
            leader_return_pct=8.5,
            leader_volume_ratio=2.1,
        )
    )
    db.commit()

    resp = client.get("/api/leader-follower/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["signals"]) == 1
    assert data.get("diagnostics") is None

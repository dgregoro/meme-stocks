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
from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.models.leader_event import LeaderEvent
from backend.app.models.leader_follower_candidate import LeaderFollowerCandidate
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock


def _seed_min_research_footprint(db: Session) -> None:
    db.add(Stock(symbol="XXX", name="X", sector=None, market_cap=None))
    db.add(
        PriceData(
            stock_symbol="XXX",
            date=date(2024, 1, 2),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1,
        )
    )
    db.commit()


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
    """GET /api/leader-follower/status returns no_leaders when metrics show zero leaders (grouped universe non-empty)."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 25,
        "grouped_leader_universe_size": 10,
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
        "grouped_leader_universe_size": 10,
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
def test_status_includes_grouped_leader_universe_size() -> None:
    """GET /api/leader-follower/status returns stage_counts.grouped_leader_universe_size when run has metrics."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 1600,
        "grouped_leader_universe_size": 42,
        "leader_events_detected": 2,
        "follower_candidates_found": 5,
        "signals_emitted": 3,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=2.0,
            success=True,
            error_message=None,
            summary="ok",
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage_counts"]["grouped_leader_universe_size"] == 42
    assert data["stage_counts"]["input_universe_size"] == 1600


@pytest.mark.integration
def test_status_stock_groups_empty_returns_stock_groups_empty_reason() -> None:
    """GET /api/leader-follower/status returns empty_reason stock_groups_empty when grouped_leader_universe_size is 0."""
    client, db = _create_test_app()
    metrics = {
        "input_universe_size": 1600,
        "grouped_leader_universe_size": 0,
        "leader_events_detected": 0,
        "follower_candidates_found": 0,
        "signals_emitted": 0,
    }
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 21, 17, 0, 0, tzinfo=timezone.utc),
            duration_seconds=0.5,
            success=True,
            error_message=None,
            summary="short-circuited: no stock groups",
            metrics_json=json.dumps(metrics),
        )
    )
    db.commit()
    resp = client.get("/api/leader-follower/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["empty_reason"] == "stock_groups_empty"
    assert data["stage_counts"]["grouped_leader_universe_size"] == 0


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
def test_runs_with_date_filters_and_near_miss_count() -> None:
    """GET /api/leader-follower/runs?since_date=X&until_date=Y filters by run_at; near_miss_count in metrics."""
    client, db = _create_test_app()
    metrics_in_range = {
        "input_universe_size": 25,
        "leader_events_detected": 1,
        "near_miss_count": 8,
        "signals_emitted": 2,
    }
    metrics_out_range = {"input_universe_size": 25, "leader_events_detected": 0}
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 20, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 20, 17, 0, 0, tzinfo=timezone.utc),
            success=True,
            metrics_json=json.dumps(metrics_out_range),
        )
    )
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
            success=True,
            metrics_json=json.dumps(metrics_in_range),
        )
    )
    db.add(
        JobRunHistory(
            job_name="leader_follower_detection",
            run_at=datetime(2026, 3, 24, 17, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 3, 24, 17, 0, 0, tzinfo=timezone.utc),
            success=True,
            metrics_json=json.dumps(metrics_out_range),
        )
    )
    db.commit()

    resp = client.get("/api/leader-follower/runs?since_date=2026-03-22&until_date=2026-03-22&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert "2026-03-22" in run["run_at"]
    assert run["metrics"].get("near_miss_count") == 8

    resp2 = client.get("/api/leader-follower/runs?since_date=2026-03-21&until_date=2026-03-23&limit=10")
    assert resp2.status_code == 200
    assert len(resp2.json()["runs"]) == 1


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

    # Add a run with no_leaders metrics (grouped universe non-empty); still no signals → diagnostics with run info
    metrics = {
        "input_universe_size": 25,
        "grouped_leader_universe_size": 10,
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


@pytest.mark.integration
def test_leader_debug_returns_evaluations() -> None:
    """GET /api/leader-follower/leader-debug returns evaluations for run; 404 when run missing."""
    client, db = _create_test_app()
    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
        metrics_json=json.dumps({"event_date": "2026-03-22", "leader_events_detected": 1}),
    )
    db.add(run)
    db.flush()
    db.add(
        LeaderDebugEvaluation(
            job_run_id=run.id,
            stock_symbol="GME",
            return_pct=2.1,
            volume_ratio=1.3,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["below_return_threshold", "insufficient_volume"]),
        )
    )
    db.add(
        LeaderDebugEvaluation(
            job_run_id=run.id,
            stock_symbol="NVDA",
            return_pct=None,
            volume_ratio=None,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["insufficient_bars"]),
        )
    )
    db.add(
        LeaderDebugEvaluation(
            job_run_id=run.id,
            stock_symbol="AAPL",
            return_pct=6.0,
            volume_ratio=2.0,
            qualified_as_leader=True,
            rejection_reasons=json.dumps([]),
        )
    )
    db.commit()

    resp = client.get(f"/api/leader-follower/leader-debug?run_id={run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run.id
    assert data["event_date"] == "2026-03-22"
    assert data["evaluated_count"] == 3
    assert data["leaders_count"] == 1
    assert len(data["evaluations"]) == 3
    gme = next(e for e in data["evaluations"] if e["symbol"] == "GME")
    assert gme["return_pct"] == 2.1
    assert gme["volume_ratio"] == 1.3
    assert gme["qualified_as_leader"] is False
    assert set(gme["rejection_reasons"]) == {"below_return_threshold", "insufficient_volume"}

    resp404 = client.get("/api/leader-follower/leader-debug?run_id=99999")
    assert resp404.status_code == 404


@pytest.mark.integration
def test_leader_debug_empty_when_no_data() -> None:
    """GET /api/leader-follower/leader-debug returns 200 with empty evaluations when run has no debug data."""
    client, db = _create_test_app()
    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
        metrics_json=json.dumps({"event_date": "2026-03-22"}),
    )
    db.add(run)
    db.flush()
    db.commit()

    resp = client.get(f"/api/leader-follower/leader-debug?run_id={run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluated_count"] == 0
    assert data["leaders_count"] == 0
    assert data["evaluations"] == []


@pytest.mark.integration
def test_leader_near_miss_returns_near_misses() -> None:
    """GET /api/leader-follower/leader-near-miss returns near-misses; 404 when run missing."""
    client, db = _create_test_app()
    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
    )
    db.add(run)
    db.flush()
    db.add(
        LeaderDebugEvaluation(
            job_run_id=run.id,
            stock_symbol="GME",
            return_pct=4.2,
            volume_ratio=1.4,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["below_return_threshold", "insufficient_volume"]),
            metrics_json=json.dumps({"return_threshold": 5.0, "volume_threshold": 1.5}),
        )
    )
    db.add(
        LeaderDebugEvaluation(
            job_run_id=run.id,
            stock_symbol="NVDA",
            return_pct=2.1,
            volume_ratio=0.9,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["below_return_threshold", "insufficient_volume"]),
            metrics_json=json.dumps({"return_threshold": 5.0, "volume_threshold": 1.5}),
        )
    )
    db.commit()

    resp = client.get(f"/api/leader-follower/leader-near-miss?run_id={run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run.id
    assert len(data["near_misses"]) == 2
    assert data["near_misses"][0]["symbol"] == "GME"
    assert data["near_misses"][0]["return_pct"] == 4.2
    assert data["near_misses"][0]["return_threshold"] == 5.0
    assert data["near_misses"][0]["volume_threshold"] == 1.5

    resp404 = client.get("/api/leader-follower/leader-near-miss?run_id=99999")
    assert resp404.status_code == 404


@pytest.mark.integration
def test_leader_near_miss_empty_when_none() -> None:
    """GET /api/leader-follower/leader-near-miss returns 200 with empty when no near-misses."""
    client, db = _create_test_app()
    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2026, 3, 22, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
    )
    db.add(run)
    db.flush()
    db.commit()

    resp = client.get(f"/api/leader-follower/leader-near-miss?run_id={run.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["near_misses"] == []


# --- Evaluation endpoints (007) ---


@pytest.mark.unit
def test_evaluation_summary_database_unready() -> None:
    client, _ = _create_test_app()
    resp = client.get("/api/leader-follower/evaluation/summary")
    assert resp.status_code == 503
    assert resp.json().get("error_type") == "DATABASE_UNREADY"


@pytest.mark.unit
def test_evaluation_summary_empty() -> None:
    """GET /api/leader-follower/evaluation/summary returns zeros when no signals."""
    client, db = _create_test_app()
    _seed_min_research_footprint(db)
    resp = client.get("/api/leader-follower/evaluation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_signals"] == 0
    assert data["signals_per_day"] == 0.0
    assert "by_horizon" in data
    assert "1d" in data["by_horizon"]
    assert data["by_horizon"]["1d"]["evaluable_count"] == 0
    assert "duplicate_overlap" in data
    assert data["duplicate_overlap"]["repeat_pair_in_window"] == 0


@pytest.mark.unit
def test_evaluation_summary_with_signal_and_prices() -> None:
    """GET /api/leader-follower/evaluation/summary returns metrics when signal and price data exist."""
    from backend.app.models.price_data import PriceData

    client, db = _create_test_app()
    db.add(Stock(symbol="INTC", name="Intel", sector="Tech", market_cap=None))
    db.add(Stock(symbol="QCOM", name="Qualcomm", sector="Tech", market_cap=None))
    db.commit()
    for d, c in [(date(2026, 3, 1), 50.0), (date(2026, 3, 2), 51.0), (date(2026, 3, 3), 52.0)]:
        db.add(
            PriceData(
                stock_symbol="QCOM",
                date=d,
                open=c - 0.5,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=1_000_000,
            )
        )
    db.add(
        LeaderFollowerSignal(
            leader_symbol="INTC",
            follower_symbol="QCOM",
            group_id="semis",
            signal_date=date(2026, 3, 1),
            strength_score=1.0,
            leader_return_pct=5.0,
            leader_volume_ratio=1.5,
        )
    )
    db.commit()

    resp = client.get("/api/leader-follower/evaluation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_signals"] == 1
    assert data["by_horizon"]["1d"]["evaluable_count"] == 1
    assert data["by_horizon"]["1d"]["avg_return_pct"] == 2.0  # 51/50 - 1 = 2%
    assert data["by_horizon"]["1d"]["win_rate"] == 1.0


@pytest.mark.unit
def test_evaluation_pairs_and_signals_empty() -> None:
    """GET /evaluation/pairs and /evaluation/signals return empty lists when no signals."""
    client, db = _create_test_app()
    _seed_min_research_footprint(db)
    resp_pairs = client.get("/api/leader-follower/evaluation/pairs")
    assert resp_pairs.status_code == 200
    assert resp_pairs.json()["pairs"] == []
    resp_signals = client.get("/api/leader-follower/evaluation/signals")
    assert resp_signals.status_code == 200
    assert resp_signals.json()["signals"] == []


# --- Pairs filtering and ranking (009) ---


def _seed_evaluation_data(db: Session) -> None:
    """Seed stocks, price data, and signals for pairs evaluation tests."""
    from backend.app.models.price_data import PriceData

    db.add(Stock(symbol="INTC", name="Intel", sector="Tech", market_cap=None))
    db.add(Stock(symbol="QCOM", name="Qualcomm", sector="Tech", market_cap=None))
    db.add(Stock(symbol="NVDA", name="NVIDIA", sector="Tech", market_cap=None))
    db.commit()
    for d, c in [
        (date(2026, 3, 1), 50.0),
        (date(2026, 3, 2), 51.0),
        (date(2026, 3, 3), 52.0),
        (date(2026, 3, 4), 53.0),
        (date(2026, 3, 5), 54.0),
        (date(2026, 3, 6), 55.0),
    ]:
        for sym in ("QCOM", "NVDA"):
            db.add(
                PriceData(
                    stock_symbol=sym,
                    date=d,
                    open=c - 0.5,
                    high=c + 0.5,
                    low=c - 0.5,
                    close=c,
                    volume=1_000_000,
                )
            )
    db.add(
        LeaderFollowerSignal(
            leader_symbol="INTC",
            follower_symbol="QCOM",
            group_id="semis",
            signal_date=date(2026, 3, 1),
            strength_score=1.0,
            leader_return_pct=5.0,
            leader_volume_ratio=1.5,
        )
    )
    db.add(
        LeaderFollowerSignal(
            leader_symbol="INTC",
            follower_symbol="QCOM",
            group_id="semis",
            signal_date=date(2026, 3, 2),
            strength_score=0.9,
            leader_return_pct=3.0,
            leader_volume_ratio=1.2,
        )
    )
    db.add(
        LeaderFollowerSignal(
            leader_symbol="INTC",
            follower_symbol="NVDA",
            group_id="semis",
            signal_date=date(2026, 3, 1),
            strength_score=0.8,
            leader_return_pct=4.0,
            leader_volume_ratio=1.1,
        )
    )
    db.commit()


@pytest.mark.unit
def test_pairs_ranked_empty() -> None:
    """GET /pairs/ranked returns empty when no signals."""
    client, db = _create_test_app()
    _seed_min_research_footprint(db)
    resp = client.get("/api/leader-follower/pairs/ranked")
    assert resp.status_code == 200
    data = resp.json()
    assert "pairs" in data
    assert data["pairs"] == []


@pytest.mark.unit
def test_pairs_ranked_with_data() -> None:
    """GET /pairs/ranked returns pairs sorted by avg_return_1d desc by default."""
    client, db = _create_test_app()
    _seed_evaluation_data(db)
    resp = client.get("/api/leader-follower/pairs/ranked")
    assert resp.status_code == 200
    data = resp.json()
    assert "pairs" in data
    pairs = data["pairs"]
    assert len(pairs) >= 1
    for p in pairs:
        assert "leader_symbol" in p
        assert "follower_symbol" in p
        assert "signal_count" in p
        assert "1d" in p
    # Default sort: avg_return_1d desc; higher avg first
    for i in range(len(pairs) - 1):
        curr = pairs[i].get("1d", {}) or {}
        next_p = pairs[i + 1].get("1d", {}) or {}
        curr_avg = float(curr.get("avg_return_pct", 0) or 0)
        next_avg = float(next_p.get("avg_return_pct", 0) or 0)
        assert curr_avg >= next_avg


@pytest.mark.unit
def test_pairs_ranked_sort_order() -> None:
    """GET /pairs/ranked respects sort_by and sort_order query params."""
    client, db = _create_test_app()
    _seed_evaluation_data(db)
    resp = client.get("/api/leader-follower/pairs/ranked?sort_by=signal_count&sort_order=asc")
    assert resp.status_code == 200
    pairs = resp.json()["pairs"]
    for i in range(len(pairs) - 1):
        assert pairs[i]["signal_count"] <= pairs[i + 1]["signal_count"]


@pytest.mark.unit
def test_pairs_ranked_invalid_sort_by() -> None:
    """GET /pairs/ranked returns 400 for invalid sort_by."""
    client, db = _create_test_app()
    _seed_evaluation_data(db)
    resp = client.get("/api/leader-follower/pairs/ranked?sort_by=invalid_field")
    assert resp.status_code == 400


@pytest.mark.unit
def test_pairs_filtered_empty() -> None:
    """GET /pairs/filtered returns empty when no signals."""
    client, db = _create_test_app()
    _seed_min_research_footprint(db)
    resp = client.get("/api/leader-follower/pairs/filtered")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pairs"] == []
    assert data["total_before_filter"] == 0
    assert data["total_after_filter"] == 0


@pytest.mark.unit
def test_pairs_filtered_with_data() -> None:
    """GET /pairs/filtered returns pairs with filter_status and metadata."""
    client, db = _create_test_app()
    _seed_evaluation_data(db)
    resp = client.get("/api/leader-follower/pairs/filtered")
    assert resp.status_code == 200
    data = resp.json()
    assert "pairs" in data
    assert "total_before_filter" in data
    assert "total_after_filter" in data
    assert data["total_before_filter"] >= data["total_after_filter"]
    for p in data["pairs"]:
        assert p["filter_status"] in ("pass", "fail", "insufficient_data")
        assert "thresholds_applied" in p


@pytest.mark.unit
def test_pairs_filtered_threshold_overrides() -> None:
    """GET /pairs/filtered respects min_signal_count override."""
    client, db = _create_test_app()
    _seed_evaluation_data(db)
    resp = client.get("/api/leader-follower/pairs/filtered?min_signal_count=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_after_filter"] == 0


@pytest.mark.unit
def test_pairs_blacklist() -> None:
    """GET /pairs/blacklist returns empty list for MVP."""
    client, _ = _create_test_app()
    resp = client.get("/api/leader-follower/pairs/blacklist")
    assert resp.status_code == 200
    data = resp.json()
    assert "pairs" in data
    assert data["pairs"] == []

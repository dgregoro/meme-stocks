"""API tests for leader-follower walk-forward optimization."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.leader_follower_optimization_result import LeaderFollowerOptimizationResult
from backend.app.models.leader_follower_optimization_run import LeaderFollowerOptimizationRun
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
def test_optimization_runs_list_and_top_results() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="G", sector=None, market_cap=None))
    db.commit()

    run = LeaderFollowerOptimizationRun(
        config_json="{}",
        train_start=date(2025, 1, 1),
        train_end=date(2025, 6, 30),
        validate_start=date(2025, 7, 1),
        validate_end=date(2025, 9, 30),
        test_start=None,
        test_end=None,
        ranking_method="walk_forward_v1",
    )
    db.add(run)
    db.flush()
    db.add(
        LeaderFollowerOptimizationResult(
            run_id=run.id,
            params_json='{"holding_days": 3}',
            train_metrics_json="{}",
            validate_metrics_json="{}",
            test_metrics_json=None,
            robustness_score=1.5,
            rank=1,
        )
    )
    db.commit()

    r = client.get("/api/leader-follower/optimization/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data["runs"]) == 1
    assert data["runs"][0]["result_count"] == 1

    d = client.get(f"/api/leader-follower/optimization/{run.id}")
    assert d.status_code == 200

    top = client.get(f"/api/leader-follower/optimization/{run.id}/top-results?limit=5")
    assert top.status_code == 200
    body = top.json()
    assert body["run_id"] == run.id
    assert len(body["results"]) == 1
    assert body["results"][0]["rank"] == 1


@pytest.mark.unit
def test_optimization_run_not_found() -> None:
    client, _ = _create_test_app()
    r = client.get("/api/leader-follower/optimization/99999")
    assert r.status_code == 404

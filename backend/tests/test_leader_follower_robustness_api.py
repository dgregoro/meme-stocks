"""API tests for leader-follower rolling robustness."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.main import create_app
from backend.app.models.leader_follower_robustness_aggregate import LeaderFollowerRobustnessAggregate
from backend.app.models.leader_follower_robustness_run import LeaderFollowerRobustnessRun
from backend.app.models.leader_follower_robustness_split_result import LeaderFollowerRobustnessSplitResult
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
def test_robustness_runs_list_and_detail() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="G", sector=None, market_cap=None))
    db.commit()

    run = LeaderFollowerRobustnessRun(
        overall_start=date(2024, 1, 1),
        overall_end=date(2025, 1, 1),
        train_window_spec='{"unit":"months","value":6}',
        validate_window_spec='{"unit":"months","value":2}',
        test_window_spec=None,
        step_spec='{"unit":"months","value":1}',
        split_count=2,
        grid_config_json='{"rolling":{"split_count":2}}',
        ranking_method="rolling_robustness_v1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    db.flush()
    db.add(
        LeaderFollowerRobustnessSplitResult(
            run_id=run.id,
            config_hash="a" * 64,
            params_json='{"holding_days":3}',
            split_index=0,
            train_start=date(2024, 1, 1),
            train_end=date(2024, 6, 30),
            validate_start=date(2024, 7, 1),
            validate_end=date(2024, 8, 31),
            test_start=None,
            test_end=None,
            train_metrics_json="{}",
            validate_metrics_json="{}",
            test_metrics_json=None,
        )
    )
    db.add(
        LeaderFollowerRobustnessAggregate(
            run_id=run.id,
            config_hash="a" * 64,
            params_json='{"holding_days":3}',
            aggregate_metrics_json='{"splits_evaluated":2}',
            robustness_score=1.2,
            rank=1,
        )
    )
    db.commit()

    r = client.get("/api/leader-follower/robustness/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data["runs"]) == 1
    assert data["runs"][0]["split_result_row_count"] == 1
    assert data["runs"][0]["aggregate_count"] == 1

    d = client.get(f"/api/leader-follower/robustness/{run.id}")
    assert d.status_code == 200
    body = d.json()
    assert body["split_count"] == 2
    assert body["ranking_method"] == "rolling_robustness_v1"

    tr = client.get(f"/api/leader-follower/robustness/{run.id}/top-results")
    assert tr.status_code == 200
    assert len(tr.json()["results"]) == 1

    sp = client.get(f"/api/leader-follower/robustness/{run.id}/splits?split_index=0")
    assert sp.status_code == 200
    assert len(sp.json()["items"]) == 1

    nf = client.get("/api/leader-follower/robustness/99999")
    assert nf.status_code == 404

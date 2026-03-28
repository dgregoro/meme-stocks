"""API tests for leader-follower paper trading."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base, get_session
from backend.app.models.leader_follower_paper_run import LeaderFollowerPaperRun
from backend.app.models.leader_follower_paper_trade import LeaderFollowerPaperTrade
from backend.app.models.stock import Stock
from backend.app.main import create_app


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
def test_paper_trading_runs_list_and_detail() -> None:
    client, db = _create_test_app()
    db.add(Stock(symbol="GME", name="G", sector=None, market_cap=None))
    db.commit()

    run = LeaderFollowerPaperRun(
        config_json='{"entry_mode": "next_open"}',
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        total_trades=1,
        skipped_count=0,
        skipped_sector_confirmation_count=0,
        skipped_regime_filter_count=0,
        win_rate=1.0,
        avg_return_pct=0.5,
        cumulative_return_pct=0.5,
        max_drawdown_pct=0.0,
    )
    db.add(run)
    db.flush()
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db.add(
        LeaderFollowerPaperTrade(
            run_id=run.id,
            leader_symbol="GME",
            follower_symbol="GME",
            signal_date=date(2026, 1, 15),
            signal_id=None,
            entry_price=100.0,
            exit_price=101.0,
            entry_time=t0,
            exit_time=t0,
            holding_period_days=3,
            gross_return_pct=1.0,
            net_return_pct=0.9,
            regime_benchmark_symbol="SPY",
            regime_decision_date=date(2026, 1, 15),
            regime_benchmark_close=450.0,
            regime_benchmark_ma=440.0,
            regime_market_uptrend_passed=True,
            regime_volatility=0.012,
            regime_low_volatility_passed=True,
            regime_sector_strength_passed=None,
            regime_filter_passed=True,
        )
    )
    db.commit()

    r = client.get("/api/leader-follower/paper-trading/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data["runs"]) == 1
    assert data["runs"][0]["skipped_regime_filter_count"] == 0

    r2 = client.get(f"/api/leader-follower/paper-trading/{run.id}")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["total_trades"] == 1
    assert d2["skipped_regime_filter_count"] == 0
    assert len(d2["trades"]) == 1
    tr = d2["trades"][0]
    assert tr["regime_benchmark_symbol"] == "SPY"
    assert tr["regime_decision_date"] == "2026-01-15"
    assert tr["regime_benchmark_close"] == 450.0
    assert tr["regime_benchmark_ma"] == 440.0
    assert tr["regime_market_uptrend_passed"] is True
    assert tr["regime_volatility"] == 0.012
    assert tr["regime_low_volatility_passed"] is True
    assert tr["regime_sector_strength_passed"] is None
    assert tr["regime_filter_passed"] is True

    r3 = client.get(f"/api/leader-follower/paper-trading/{run.id}/equity-curve")
    assert r3.status_code == 200
    assert len(r3.json()["points"]) == 1


@pytest.mark.unit
def test_paper_trading_run_not_found() -> None:
    client, _ = _create_test_app()
    r = client.get("/api/leader-follower/paper-trading/99999")
    assert r.status_code == 404

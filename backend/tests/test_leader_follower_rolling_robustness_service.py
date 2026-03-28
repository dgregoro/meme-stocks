"""Tests for rolling robustness service (mocked paper metrics)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base
from backend.app.models.leader_follower_robustness_aggregate import LeaderFollowerRobustnessAggregate
from backend.app.models import leader_follower_robustness_run as _lf_rob_run  # noqa: F401
from backend.app.models.leader_follower_robustness_split_result import LeaderFollowerRobustnessSplitResult
from backend.app.services.leader_follower_paper_trading_service import PaperSimulationMetrics
from backend.app.services.leader_follower_rolling_robustness_service import (
    RANKING_ROLLING_ROBUSTNESS_V1,
    RollingRobustnessValidationError,
    load_rolling_source_payload,
    run_rolling_robustness_evaluation,
)


def _mem_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _fake_metrics(ret: float, trades: int = 10) -> PaperSimulationMetrics:
    return PaperSimulationMetrics(
        total_trades=trades,
        skipped_count=0,
        skipped_sector_confirmation_count=0,
        skipped_regime_filter_count=0,
        win_rate=0.5,
        avg_return_pct=ret / max(trades, 1),
        cumulative_return_pct=ret,
        max_drawdown_pct=1.0,
    )


@pytest.mark.unit
def test_load_source_requires_rolling_method() -> None:
    with pytest.raises(RollingRobustnessValidationError, match="ranking.method"):
        load_rolling_source_payload(
            {
                "grid": {"holding_days": [1]},
                "ranking": {"method": "walk_forward_v1"},
            },
            max_grid_points=64,
        )


@pytest.mark.unit
def test_work_cap_enforced() -> None:
    db = _mem_db()
    try:
        payload = {
            "base_config": {"entry_mode": "next_open", "exit_mode": "fixed_days"},
            "grid": {"holding_days": [1, 2, 3, 4]},
            "ranking": {"method": RANKING_ROLLING_ROBUSTNESS_V1},
        }
        from backend.app.config import Settings

        settings = Settings(leader_follower_robustness_max_evaluations=3)
        with pytest.raises(RollingRobustnessValidationError, match="Work size"):
            run_rolling_robustness_evaluation(
                db,
                overall_start=date(2024, 1, 1),
                overall_end=date(2026, 12, 31),
                train_months=2,
                validate_months=1,
                test_months=None,
                step_months=2,
                source_payload=payload,
                settings=settings,
            )
    finally:
        db.close()


@pytest.mark.unit
@patch(
    "backend.app.services.leader_follower_rolling_robustness_service.compute_paper_trading_metrics",
    autospec=True,
)
def test_run_persists_splits_and_ranks(mock_compute: MagicMock) -> None:
    def _side_effect(_db: Session, _start: date, _end: date, _cfg: object) -> PaperSimulationMetrics:
        return _fake_metrics(2.0)

    mock_compute.side_effect = _side_effect

    db = _mem_db()
    try:
        payload = {
            "base_config": {"entry_mode": "next_open", "exit_mode": "fixed_days"},
            "grid": {"holding_days": [3]},
            "ranking": {"method": RANKING_ROLLING_ROBUSTNESS_V1},
        }
        run = run_rolling_robustness_evaluation(
            db,
            overall_start=date(2024, 1, 1),
            overall_end=date(2025, 6, 30),
            train_months=3,
            validate_months=2,
            test_months=None,
            step_months=6,
            source_payload=payload,
        )
        assert run.split_count >= 1
        n_splits = db.query(LeaderFollowerRobustnessSplitResult).filter_by(run_id=run.id).count()
        assert n_splits == run.split_count
        n_agg = db.query(LeaderFollowerRobustnessAggregate).filter_by(run_id=run.id).count()
        assert n_agg == 1
        top = db.query(LeaderFollowerRobustnessAggregate).filter_by(run_id=run.id).one()
        assert top.rank == 1
        assert top.robustness_score > 0
    finally:
        db.close()


@pytest.mark.unit
def test_candidates_mode_loads() -> None:
    pts, ranking, snap = load_rolling_source_payload(
        {
            "base_config": {"entry_mode": "next_open", "exit_mode": "fixed_days"},
            "candidates": [{"holding_days": 3}, {"holding_days": 5}],
            "ranking": {"method": RANKING_ROLLING_ROBUSTNESS_V1},
        },
        max_grid_points=32,
    )
    assert len(pts) == 2
    assert snap["mode"] == "candidates"
    assert ranking["method"] == RANKING_ROLLING_ROBUSTNESS_V1

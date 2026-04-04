"""Tests for near_miss_leader_analysis_service."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.main import create_app  # noqa: F401
from backend.app.data.database import Base
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.models.leader_event import LeaderEvent
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.near_miss_leader_analysis_service import run_near_miss_upgrade_analysis


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


@pytest.mark.unit
def test_near_miss_upgrade_counts_upgrade_within_horizon() -> None:
    """After a near-miss day, a qualified leader on the next bar counts as upgrade."""
    db = _session()
    try:
        db.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
        t0 = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)
        run = JobRunHistory(
            job_name="leader_follower_replay",
            run_at=t0,
            success=True,
            error_message=None,
            metrics_json='{"event_date":"2026-03-14","leader_events_detected":0}',
        )
        db.add(run)
        db.flush()
        rid = run.id
        db.add(
            LeaderDebugEvaluation(
                job_run_id=rid,
                stock_symbol="GME",
                return_pct=4.0,
                volume_ratio=1.3,
                qualified_as_leader=False,
                rejection_reasons='["below_return_threshold"]',
            )
        )
        d0 = date(2026, 3, 14)
        for offset, d in enumerate(
            [
                date(2026, 3, 10),
                date(2026, 3, 11),
                date(2026, 3, 12),
                date(2026, 3, 13),
                d0,
                date(2026, 3, 15),
                date(2026, 3, 16),
                date(2026, 3, 17),
                date(2026, 3, 18),
                date(2026, 3, 19),
            ]
        ):
            db.add(
                PriceData(
                    stock_symbol="GME",
                    date=d,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0 + offset * 0.1,
                    volume=1_000_000,
                )
            )
        db.add(
            LeaderEvent(
                leader_symbol="GME",
                event_date=date(2026, 3, 15),
                return_pct=6.0,
                volume_ratio=2.0,
                direction="up",
                job_run_id=None,
            )
        )
        db.commit()

        out = run_near_miss_upgrade_analysis(
            db,
            since_date=date(2026, 3, 1),
            until_date=date(2026, 3, 31),
            horizon_sessions=5,
        )
        assert out["runs_in_window"] == 1
        assert out["near_miss_symbol_days_unique"] == 1
        assert out["eligible"] == 1
        assert out["incomplete_horizon"] == 0
        assert out["upgrades_within_horizon"] == 1
        assert out["upgrade_rate"] == pytest.approx(1.0)
    finally:
        db.close()


@pytest.mark.unit
def test_near_miss_upgrade_empty_window() -> None:
    db = _session()
    try:
        out = run_near_miss_upgrade_analysis(
            db,
            since_date=date(2024, 1, 1),
            until_date=date(2024, 1, 31),
            horizon_sessions=3,
        )
        assert out["runs_in_window"] == 0
        assert out["upgrade_rate"] is None
    finally:
        db.close()


@pytest.mark.unit
def test_near_miss_upgrade_invalid_horizon_raises() -> None:
    db = _session()
    try:
        with pytest.raises(ValueError, match="horizon_sessions"):
            run_near_miss_upgrade_analysis(
                db,
                since_date=date(2024, 1, 1),
                until_date=date(2024, 1, 31),
                horizon_sessions=0,
            )
    finally:
        db.close()

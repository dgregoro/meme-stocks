"""Tests for leader-follower evaluation service."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.models.price_data import PriceData
from backend.app.services.leader_follower_evaluation_service import (
    aggregate_summary,
    compute_duplicate_overlap,
    compute_forward_return,
    evaluate_signal,
    get_entry_price,
    run_evaluation,
)


@pytest.mark.unit
def test_compute_forward_return_missing_symbol() -> None:
    """Missing symbol returns None."""
    price_by_symbol: dict[str, list[tuple[date, float]]] = {}
    assert compute_forward_return("MISS", date(2026, 3, 1), 1, price_by_symbol) is None


@pytest.mark.unit
def test_compute_forward_return_happy_path() -> None:
    """Forward return computed correctly for trading days."""
    # 3 trading days: Mar 2, 3, 4
    price_by_symbol = {
        "TEST": [
            (date(2026, 3, 2), 100.0),
            (date(2026, 3, 3), 102.0),
            (date(2026, 3, 4), 105.0),
        ]
    }
    # 1d: 102/100 - 1 = 0.02 -> 2%
    assert compute_forward_return("TEST", date(2026, 3, 2), 1, price_by_symbol) == 2.0
    # 2d: 105/100 - 1 = 0.05 -> 5%
    assert compute_forward_return("TEST", date(2026, 3, 2), 2, price_by_symbol) == 5.0


@pytest.mark.unit
def test_compute_forward_return_insufficient_horizon() -> None:
    """Returns None when target date beyond available data."""
    price_by_symbol = {"X": [(date(2026, 3, 1), 100.0)]}
    assert compute_forward_return("X", date(2026, 3, 1), 5, price_by_symbol) is None


@pytest.mark.unit
def test_get_entry_price_missing() -> None:
    """Missing price returns None."""
    price_by_symbol: dict[str, list[tuple[date, float]]] = {}
    assert get_entry_price("X", date(2026, 3, 1), price_by_symbol) is None


@pytest.mark.unit
def test_get_entry_price_happy() -> None:
    """Entry price returns close on signal date."""
    price_by_symbol = {"Y": [(date(2026, 3, 1), 99.5)]}
    assert get_entry_price("Y", date(2026, 3, 1), price_by_symbol) == 99.5


@pytest.mark.unit
def test_compute_duplicate_overlap_empty() -> None:
    """Empty signals returns zero overlap."""
    assert compute_duplicate_overlap([], 5) == {"repeat_pair_in_window": 0, "window_days": 5}


@pytest.mark.unit
def test_compute_duplicate_overlap_repeats() -> None:
    """Same pair within window counted as repeat."""
    from unittest.mock import MagicMock

    def mk(leader: str, follower: str, d: date, i: int) -> LeaderFollowerSignal:
        s = MagicMock(spec=LeaderFollowerSignal)
        s.leader_symbol = leader
        s.follower_symbol = follower
        s.signal_date = d
        s.id = i
        return s

    # Two signals same pair, 3 days apart
    sigs = [
        mk("A", "B", date(2026, 3, 1), 1),
        mk("A", "B", date(2026, 3, 4), 2),
    ]
    out = compute_duplicate_overlap(sigs, 5)
    assert out["repeat_pair_in_window"] == 1
    assert out["window_days"] == 5


@pytest.mark.integration
def test_run_evaluation_empty_db() -> None:
    """No signals returns empty list."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        signals, price_by_symbol, horizons = run_evaluation(db)
        assert signals == []
        assert price_by_symbol == {}
        assert horizons == (1, 3, 5)
    finally:
        db.close()


@pytest.mark.integration
def test_aggregate_summary_empty() -> None:
    """Empty signals returns zeros."""
    summary = aggregate_summary([], {})
    assert summary["total_signals"] == 0
    assert summary["signals_per_day"] == 0.0
    assert "1d" in summary["by_horizon"]
    assert summary["by_horizon"]["1d"]["evaluable_count"] == 0
    assert summary["duplicate_overlap"]["repeat_pair_in_window"] == 0


@pytest.mark.integration
def test_evaluate_signal_and_aggregate_with_price_data() -> None:
    """End-to-end: add signal and price data, run evaluation."""
    from backend.app.models.stock import Stock

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Stock(symbol="INTC", name="Intel", sector="Tech", market_cap=None))
        db.add(Stock(symbol="QCOM", name="Qualcomm", sector="Tech", market_cap=None))
        db.commit()

        price_repo = PriceDataRepository(db)
        for d, c in [
            (date(2026, 3, 1), 50.0),
            (date(2026, 3, 2), 51.0),
            (date(2026, 3, 3), 52.0),
            (date(2026, 3, 4), 53.0),
            (date(2026, 3, 5), 54.0),
            (date(2026, 3, 6), 55.0),
        ]:
            p = PriceData(
                stock_symbol="QCOM",
                date=d,
                open=c - 0.5,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=1_000_000,
            )
            price_repo.add(p)
        db.commit()

        sig = LeaderFollowerSignal(
            leader_symbol="INTC",
            follower_symbol="QCOM",
            group_id="semis",
            signal_date=date(2026, 3, 1),
            strength_score=1.0,
            leader_return_pct=5.0,
            leader_volume_ratio=1.5,
        )
        signal_repo = LeaderFollowerSignalRepository(db)
        signal_repo.add(sig)
        db.commit()

        signals, price_by_symbol, horizons = run_evaluation(db)
        assert len(signals) >= 1
        s = next(x for x in signals if x.follower_symbol == "QCOM" and x.signal_date == date(2026, 3, 1))
        ev = evaluate_signal(s, price_by_symbol, horizons)
        assert ev["entry_price"] == 50.0
        assert ev["1d"]["forward_return_pct"] == 2.0  # 51/50 - 1 = 2%
        assert ev["1d"]["win"] is True

        summary = aggregate_summary(signals, price_by_symbol, horizons)
        assert summary["total_signals"] >= 1
        assert summary["by_horizon"]["1d"]["evaluable_count"] >= 1
    finally:
        db.close()


@pytest.mark.unit
def test_aggregate_summary_event_level_with_clustered_signals() -> None:
    """Event-level metrics: one leader-date with multiple followers; event = avg of follower returns."""
    from backend.app.main import create_app  # noqa: F401 - ensure all models registered
    from backend.app.models.stock import Stock

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        for sym in ("INTC", "QCOM", "NVDA"):
            db.add(Stock(symbol=sym, name=sym, sector="Tech", market_cap=None))
        db.commit()

        price_repo = PriceDataRepository(db)
        # QCOM: 50->51 (2%), NVDA: 100->99 (-1%)
        for d, q, n in [
            (date(2026, 3, 1), 50.0, 100.0),
            (date(2026, 3, 2), 51.0, 99.0),
        ]:
            for sym, c in [("QCOM", q), ("NVDA", n)]:
                price_repo.add(PriceData(stock_symbol=sym, date=d, open=c, high=c, low=c, close=c, volume=1_000_000))
        db.commit()

        signal_repo = LeaderFollowerSignalRepository(db)
        for follower in ("QCOM", "NVDA"):
            signal_repo.add(
                LeaderFollowerSignal(
                    leader_symbol="INTC",
                    follower_symbol=follower,
                    group_id="semis",
                    signal_date=date(2026, 3, 1),
                    strength_score=1.0,
                    leader_return_pct=5.0,
                    leader_volume_ratio=1.5,
                )
            )
        db.commit()

        signals, price_by_symbol, horizons = run_evaluation(db)
        summary = aggregate_summary(signals, price_by_symbol, horizons)

        assert summary["total_signals"] == 2
        assert summary["total_events"] == 1
        assert summary["by_horizon"]["1d"]["evaluable_count"] == 2
        assert summary["by_horizon"]["1d"]["win_rate"] == 0.5  # 1 win, 1 loss

        by_event = summary.get("by_event", {})
        assert "1d" in by_event
        assert by_event["1d"]["event_count"] == 1
        assert by_event["1d"]["event_win_rate"] == 1.0  # avg (2, -1) = 0.5 > 0
        assert abs(by_event["1d"]["event_avg_return_pct"] - 0.5) < 0.01
    finally:
        db.close()

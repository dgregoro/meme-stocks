"""Unit tests for extreme move evaluation aggregates (016)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.extreme_move_evaluation_service import (
    aggregate_by_symbol,
    aggregate_by_type_flat,
    aggregate_evaluation_by_magnitude,
    aggregate_evaluation_by_magnitude_volume,
    aggregate_evaluation_by_volume,
    aggregate_extreme_move_summary,
    calendar_quarter_bounds,
    h2_stability_brittle_verdict,
    iter_train_calendar_quarters,
    run_extreme_move_evaluation,
    run_h2_quarterly_stability_extreme_down,
)


@pytest.mark.unit
def test_aggregate_summary_forward_return_from_event_close() -> None:
    """Known closes: ref day 100, +1 trading day 110 -> +10%."""
    d0 = date(2024, 1, 2)
    d1 = date(2024, 1, 3)
    d2 = date(2024, 1, 4)
    ev = ExtremeMoveEvent(
        symbol="T",
        event_date=d1,
        return_pct=5.0,
        event_type="extreme_up",
    )
    price_by_symbol = {
        "T": [
            (d0, 100.0),
            (d1, 100.0),
            (d2, 110.0),
        ]
    }
    summary = aggregate_extreme_move_summary([ev], price_by_symbol, horizons=(1,))
    h1 = summary["by_horizon"]["1d"]
    assert h1["evaluable_count"] == 1
    assert h1["avg_return_pct"] == 10.0
    assert h1["win_rate"] == 1.0
    up = summary["by_event_type"]["extreme_up"]["1d"]
    assert up["evaluable_count"] == 1


@pytest.mark.unit
def test_aggregate_summary_missing_forward_data() -> None:
    ev = ExtremeMoveEvent(
        symbol="T",
        event_date=date(2024, 1, 2),
        return_pct=-5.0,
        event_type="extreme_down",
    )
    price_by_symbol = {"T": [(date(2024, 1, 2), 100.0)]}
    summary = aggregate_extreme_move_summary([ev], price_by_symbol, horizons=(1, 3))
    assert summary["by_horizon"]["1d"]["evaluable_count"] == 0
    assert summary["by_horizon"]["3d"]["evaluable_count"] == 0


@pytest.mark.unit
def test_empty_events_summary() -> None:
    s = aggregate_extreme_move_summary([], {}, horizons=(1, 3))
    assert s["total_events"] == 0
    assert s["date_range"]["since"] is None


@pytest.mark.unit
def test_aggregate_by_magnitude_groups_events() -> None:
    d0 = date(2024, 1, 2)
    d1 = date(2024, 1, 3)
    ev1 = ExtremeMoveEvent(
        symbol="T",
        event_date=d1,
        return_pct=6.0,
        event_type="extreme_up",
        magnitude_bucket="5-8",
        volume_bucket="high",
    )
    ev2 = ExtremeMoveEvent(
        symbol="T",
        event_date=d1,
        return_pct=-6.0,
        event_type="extreme_down",
        magnitude_bucket="8+",
        volume_bucket="normal",
    )
    price_by_symbol = {"T": [(d0, 100.0), (d1, 100.0)]}
    by_mag = aggregate_evaluation_by_magnitude([ev1, ev2], price_by_symbol, horizons=(1,))
    assert set(by_mag.keys()) == {"5-8", "8+"}
    assert by_mag["5-8"]["total_events"] == 1
    assert by_mag["8+"]["total_events"] == 1


@pytest.mark.unit
def test_aggregate_by_magnitude_volume_composite_keys() -> None:
    d1 = date(2024, 2, 1)
    ev = ExtremeMoveEvent(
        symbol="X",
        event_date=d1,
        return_pct=7.0,
        event_type="extreme_up",
        magnitude_bucket="5-8",
        volume_bucket="extreme",
    )
    out = aggregate_evaluation_by_magnitude_volume([ev], {}, horizons=(1,))
    assert "5-8|extreme" in out
    assert out["5-8|extreme"]["total_events"] == 1


@pytest.mark.unit
def test_run_extreme_move_evaluation_loads_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_RESEARCH_HORIZONS", "1")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="EM", name="E", sector=None, market_cap=None))
        db.add(
            ExtremeMoveEvent(
                symbol="EM",
                event_date=date(2024, 1, 3),
                return_pct=6.0,
                event_type="extreme_up",
            )
        )
        for d, c in (
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 106.0),
            (date(2024, 1, 4), 110.0),
        ):
            db.add(
                PriceData(
                    stock_symbol="EM",
                    date=d,
                    open=c,
                    high=c + 1,
                    low=c - 1,
                    close=c,
                    volume=1_000_000,
                )
            )
        db.commit()
        events, prices, hz = run_extreme_move_evaluation(db)
        assert len(events) == 1
        assert hz == (1,)
        assert "EM" in prices
        assert len(prices["EM"]) == 2
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_extreme_move_evaluation_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_RESEARCH_HORIZONS", "1,7")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="NE", name="N", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="NE",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        ev, prices, hz = run_extreme_move_evaluation(db)
        assert ev == []
        assert prices == {}
        assert hz == (1, 7)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_extreme_move_horizons_invalid_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_RESEARCH_HORIZONS", "oops")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="HZ", name="H", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="HZ",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        _e, _p, hz = run_extreme_move_evaluation(db)
        assert hz == (1, 3, 5)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_aggregate_extreme_by_symbol_and_type_flat() -> None:
    ev = ExtremeMoveEvent(
        symbol="A",
        event_date=date(2024, 1, 2),
        return_pct=1.0,
        event_type="extreme_up",
    )
    prices = {"A": [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 101.0)]}
    assert aggregate_by_symbol([ev], prices, horizons=(1,), min_sample=2) == []
    rows = aggregate_by_symbol([ev], prices, horizons=(1,), min_sample=1)
    assert len(rows) == 1
    flat = aggregate_by_type_flat([ev], prices, horizons=(1,))
    full = aggregate_extreme_move_summary([ev], prices, horizons=(1,))
    assert flat == full["by_event_type"]


@pytest.mark.unit
def test_calendar_quarter_bounds_q1_q4() -> None:
    s, e = calendar_quarter_bounds(2024, 1)
    assert s == date(2024, 1, 1) and e == date(2024, 3, 31)
    s, e = calendar_quarter_bounds(2024, 3)
    assert s == date(2024, 7, 1) and e == date(2024, 9, 30)
    s, e = calendar_quarter_bounds(2024, 4)
    assert s == date(2024, 10, 1) and e == date(2024, 12, 31)


@pytest.mark.unit
def test_iter_train_calendar_quarters_respects_exclusive_train_end() -> None:
    rows = iter_train_calendar_quarters(date(2025, 2, 3))
    labels = [r[0] for r in rows]
    assert "2024-Q4" in labels
    assert "2025-Q1" not in labels
    assert rows[-1][0] == "2024-Q4"


@pytest.mark.unit
def test_h2_stability_brittle_majority_rule() -> None:
    assert h2_stability_brittle_verdict(eligible_quarters=0, eligible_non_positive_net=0) is False
    assert h2_stability_brittle_verdict(eligible_quarters=3, eligible_non_positive_net=2) is True
    assert h2_stability_brittle_verdict(eligible_quarters=3, eligible_non_positive_net=1) is False
    assert h2_stability_brittle_verdict(eligible_quarters=4, eligible_non_positive_net=2) is False
    assert h2_stability_brittle_verdict(eligible_quarters=4, eligible_non_positive_net=3) is True


def _weekdays_from(start: date, n: int) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


@pytest.mark.unit
def test_run_h2_quarterly_stability_no_train_events() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="H2", name="H", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="H2",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        out = run_h2_quarterly_stability_extreme_down(db, train_end_exclusive=date(2025, 2, 3))
        assert out["verdict"] == "inconclusive"
        assert out["quarters"] == []
        assert out.get("note")
    finally:
        db.close()


@pytest.mark.unit
def test_run_h2_quarterly_stability_two_eligible_quarters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_DEFAULT_ROUND_TRIP_COST_BPS", "10")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="S", name="S", sector=None, market_cap=None))
        # 2024-Q1: 20 rising days -> positive 1d forward
        q1_days = _weekdays_from(date(2024, 1, 2), 22)
        # 2024-Q2: 20 falling days -> negative 1d forward
        q2_days = _weekdays_from(date(2024, 4, 2), 22)

        def add_bar(d: date, close: float) -> None:
            db.add(
                PriceData(
                    stock_symbol="S",
                    date=d,
                    open=close,
                    high=close + 0.1,
                    low=close - 0.1,
                    close=close,
                    volume=1_000_000,
                )
            )

        for i, d in enumerate(q1_days[:21]):
            add_bar(d, 100.0 + i * 0.5)
        for d in q1_days[:20]:
            db.add(
                ExtremeMoveEvent(
                    symbol="S",
                    event_date=d,
                    return_pct=-6.0,
                    event_type="extreme_down",
                )
            )
        for i, d in enumerate(q2_days[:21]):
            add_bar(d, 200.0 - i * 0.5)
        for d in q2_days[:20]:
            db.add(
                ExtremeMoveEvent(
                    symbol="S",
                    event_date=d,
                    return_pct=-6.0,
                    event_type="extreme_down",
                )
            )
        db.commit()

        out = run_h2_quarterly_stability_extreme_down(
            db,
            train_end_exclusive=date(2025, 2, 3),
            horizon_k=1,
            min_evaluable=20,
        )
        assert out["eligible_quarter_count"] >= 2
        assert out["verdict"] in ("brittle", "not_brittle", "inconclusive")
        qs = {r["quarter"]: r for r in out["quarters"]}
        assert qs["2024-Q1"]["evaluable_count"] >= 20
        assert qs["2024-Q2"]["evaluable_count"] >= 20
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_aggregate_by_volume_unknown_fallback() -> None:
    d1 = date(2024, 3, 1)
    ev = ExtremeMoveEvent(
        symbol="Z",
        event_date=d1,
        return_pct=5.0,
        event_type="extreme_up",
        magnitude_bucket=None,
        volume_bucket=None,
    )
    by_vol = aggregate_evaluation_by_volume([ev], {}, horizons=(1,))
    assert "unknown" in by_vol
    assert by_vol["unknown"]["total_events"] == 1

"""Unit tests for extreme move evaluation aggregates (016)."""

from __future__ import annotations

from datetime import date

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
    run_extreme_move_evaluation,
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

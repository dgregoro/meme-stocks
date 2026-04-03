"""Unit tests for volume spike evaluation aggregates."""

from __future__ import annotations

from datetime import date

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.volume_spike_event import VolumeSpikeEvent
from backend.app.services.volume_spike_evaluation_service import (
    aggregate_by_symbol,
    aggregate_by_type_flat,
    aggregate_volume_spike_summary,
    run_volume_spike_evaluation,
)


@pytest.mark.unit
def test_aggregate_summary_forward_return_from_event_close() -> None:
    """Known closes: ref day 100, +1 trading day 110 -> +10%."""
    d0 = date(2024, 1, 2)
    d1 = date(2024, 1, 3)
    d2 = date(2024, 1, 4)
    ev = VolumeSpikeEvent(
        symbol="T",
        event_date=d1,
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_up",
    )
    price_by_symbol = {
        "T": [
            (d0, 100.0),
            (d1, 100.0),
            (d2, 110.0),
        ]
    }
    summary = aggregate_volume_spike_summary([ev], price_by_symbol, horizons=(1,))
    h1 = summary["by_horizon"]["1d"]
    assert h1["evaluable_count"] == 1
    assert h1["avg_return_pct"] == 10.0
    assert h1["win_rate"] == 1.0
    up = summary["by_event_type"]["spike_up"]["1d"]
    assert up["evaluable_count"] == 1


@pytest.mark.unit
def test_aggregate_summary_missing_forward_data() -> None:
    ev = VolumeSpikeEvent(
        symbol="T",
        event_date=date(2024, 1, 2),
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_flat",
    )
    price_by_symbol = {"T": [(date(2024, 1, 2), 100.0)]}
    summary = aggregate_volume_spike_summary([ev], price_by_symbol, horizons=(1, 3))
    assert summary["by_horizon"]["1d"]["evaluable_count"] == 0
    assert summary["by_horizon"]["3d"]["evaluable_count"] == 0


@pytest.mark.unit
def test_empty_events_summary() -> None:
    s = aggregate_volume_spike_summary([], {}, horizons=(1, 3))
    assert s["total_events"] == 0
    assert s["date_range"]["since"] is None


@pytest.mark.unit
def test_run_volume_spike_evaluation_loads_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_HORIZONS", "1")
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
        db.add(Stock(symbol="VS", name="V", sector=None, market_cap=None))
        db.add(Stock(symbol="OTHER", name="O", sector=None, market_cap=None))
        db.add(
            VolumeSpikeEvent(
                symbol="VS",
                event_date=date(2024, 1, 3),
                volume=1_000_000,
                baseline_volume=500_000.0,
                volume_ratio=2.0,
                same_day_return_pct=0.0,
                event_type="spike_up",
            )
        )
        for sym, d, c in (
            ("VS", date(2024, 1, 2), 100.0),
            ("VS", date(2024, 1, 3), 100.0),
            ("VS", date(2024, 1, 4), 110.0),
            ("OTHER", date(2024, 1, 2), 50.0),
        ):
            db.add(
                PriceData(
                    stock_symbol=sym,
                    date=d,
                    open=c,
                    high=c + 0.5,
                    low=c - 0.5,
                    close=c,
                    volume=400_000,
                )
            )
        db.commit()
        events, prices, hz = run_volume_spike_evaluation(db)
        assert len(events) == 1
        assert hz == (1,)
        assert "VS" in prices
        # Price load starts at min(event dates); rows strictly before first event are excluded.
        assert len(prices["VS"]) == 2
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_volume_spike_evaluation_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_HORIZONS", "1,5")
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
        db.add(Stock(symbol="NV", name="N", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="NV",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        ev, prices, hz = run_volume_spike_evaluation(db)
        assert ev == []
        assert prices == {}
        assert hz == (1, 5)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_horizons_env_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_HORIZONS", "not-a-number")
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
        db.add(Stock(symbol="HV", name="H", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="HV",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        _e, _p, hz = run_volume_spike_evaluation(db)
        assert hz == (1, 3, 5)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_aggregate_by_symbol_respects_min_sample() -> None:
    ev = VolumeSpikeEvent(
        symbol="ONLY",
        event_date=date(2024, 1, 2),
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_up",
    )
    prices = {"ONLY": [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 101.0)]}
    assert aggregate_by_symbol([ev], prices, horizons=(1,), min_sample=2) == []
    rows = aggregate_by_symbol([ev], prices, horizons=(1,), min_sample=1)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "ONLY"


@pytest.mark.unit
def test_aggregate_by_type_flat_matches_summary_slice() -> None:
    ev = VolumeSpikeEvent(
        symbol="T",
        event_date=date(2024, 1, 2),
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_up",
    )
    prices = {"T": [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 110.0)]}
    flat = aggregate_by_type_flat([ev], prices, horizons=(1,))
    full = aggregate_volume_spike_summary([ev], prices, horizons=(1,))
    assert flat == full["by_event_type"]

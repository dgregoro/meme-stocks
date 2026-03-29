"""Tests for extreme move backfill service (016)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.extreme_move_service import backfill_extreme_moves


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return TestSessionLocal()


@pytest.mark.integration
def test_backfill_extreme_up_upsert_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_UP_THRESHOLD_PCT", "5.0")
    monkeypatch.setenv("EXTREME_MOVE_DOWN_THRESHOLD_PCT", "5.0")
    get_settings.cache_clear()

    db = _session()
    try:
        db.add(Stock(symbol="ZZZ", name="Z", sector="Tech", market_cap=None))
        base = date(2024, 6, 3)
        for i in range(3):
            d = base + timedelta(days=i)
            close = 100.0 if i < 2 else 106.0  # last day +6% vs prior
            db.add(
                PriceData(
                    stock_symbol="ZZZ",
                    date=d,
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=close,
                    volume=1000,
                )
            )
        db.commit()

        end_d = base + timedelta(days=2)
        r1 = backfill_extreme_moves(db, end_d, end_d, symbols=["ZZZ"], replace_range=False)
        assert r1["events_upserted"] == 1
        n1 = db.query(ExtremeMoveEvent).filter(ExtremeMoveEvent.symbol == "ZZZ").count()
        assert n1 == 1

        r2 = backfill_extreme_moves(db, end_d, end_d, symbols=["ZZZ"], replace_range=False)
        assert r2["events_upserted"] == 1
        n2 = db.query(ExtremeMoveEvent).filter(ExtremeMoveEvent.symbol == "ZZZ").count()
        assert n2 == 1
    finally:
        get_settings.cache_clear()
        db.close()


@pytest.mark.integration
def test_backfill_replace_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_UP_THRESHOLD_PCT", "5.0")
    monkeypatch.setenv("EXTREME_MOVE_DOWN_THRESHOLD_PCT", "5.0")
    get_settings.cache_clear()

    db = _session()
    try:
        db.add(Stock(symbol="YYY", name="Y", sector="Tech", market_cap=None))
        base = date(2024, 7, 1)
        for i in range(3):
            d = base + timedelta(days=i)
            close = 100.0 if i < 2 else 106.0
            db.add(
                PriceData(
                    stock_symbol="YYY",
                    date=d,
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=close,
                    volume=1000,
                )
            )
        db.commit()
        end_d = base + timedelta(days=2)
        backfill_extreme_moves(db, end_d, end_d, symbols=["YYY"], replace_range=False)
        backfill_extreme_moves(db, end_d, end_d, symbols=["YYY"], replace_range=True)
        assert db.query(ExtremeMoveEvent).filter(ExtremeMoveEvent.symbol == "YYY").count() == 1
    finally:
        get_settings.cache_clear()
        db.close()


@pytest.mark.integration
def test_backfill_sets_magnitude_and_volume_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTREME_MOVE_UP_THRESHOLD_PCT", "5.0")
    monkeypatch.setenv("EXTREME_MOVE_DOWN_THRESHOLD_PCT", "5.0")
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_BASELINE_WINDOW_DAYS", "2")
    get_settings.cache_clear()

    db = _session()
    try:
        db.add(Stock(symbol="CTX", name="C", sector="Tech", market_cap=None))
        base = date(2024, 6, 3)
        rows = [
            (100.0, 1000),
            (100.0, 1000),
            (100.0, 1000),
            (106.0, 5000),
        ]
        for i, (close, vol) in enumerate(rows):
            d = base + timedelta(days=i)
            db.add(
                PriceData(
                    stock_symbol="CTX",
                    date=d,
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=close,
                    volume=vol,
                )
            )
        db.commit()
        end_d = base + timedelta(days=3)
        backfill_extreme_moves(db, end_d, end_d, symbols=["CTX"], replace_range=False)
        ev = db.query(ExtremeMoveEvent).filter(ExtremeMoveEvent.symbol == "CTX").one()
        assert ev.magnitude_bucket == "5-8"
        assert ev.volume_bucket == "extreme"
        assert ev.volume_ratio is not None and ev.volume_ratio >= 3.0
    finally:
        get_settings.cache_clear()
        db.close()


@pytest.mark.integration
def test_backfill_invalid_range_raises() -> None:
    db = _session()
    try:
        with pytest.raises(ValueError, match="start_date"):
            backfill_extreme_moves(db, date(2024, 1, 5), date(2024, 1, 1), symbols=["ZZZ"], replace_range=False)
    finally:
        db.close()

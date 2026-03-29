"""Tests for volume spike backfill service."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.volume_spike_event import VolumeSpikeEvent
from backend.app.services.volume_spike_service import backfill_volume_spikes


def _session_with_volume_spike() -> Session:
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
def test_backfill_upsert_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_BASELINE_WINDOW_DAYS", "2")
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_RATIO_THRESHOLD", "2.0")
    get_settings.cache_clear()

    db = _session_with_volume_spike()
    try:
        db.add(Stock(symbol="ZZZ", name="Z", sector="Tech", market_cap=None))
        base = date(2024, 6, 3)  # Monday
        for i in range(5):
            d = base + timedelta(days=i)
            vol = 5000 if i == 4 else 1000
            db.add(
                PriceData(
                    stock_symbol="ZZZ",
                    date=d,
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=10.0 + i * 0.01,
                    volume=vol,
                )
            )
        db.commit()

        end_d = base + timedelta(days=4)
        r1 = backfill_volume_spikes(db, end_d, end_d, symbols=["ZZZ"], replace_range=False)
        assert r1["events_upserted"] == 1
        n1 = db.query(VolumeSpikeEvent).filter(VolumeSpikeEvent.symbol == "ZZZ").count()
        assert n1 == 1

        r2 = backfill_volume_spikes(db, end_d, end_d, symbols=["ZZZ"], replace_range=False)
        assert r2["events_upserted"] == 1
        n2 = db.query(VolumeSpikeEvent).filter(VolumeSpikeEvent.symbol == "ZZZ").count()
        assert n2 == 1
    finally:
        get_settings.cache_clear()
        db.close()


@pytest.mark.integration
def test_backfill_replace_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_BASELINE_WINDOW_DAYS", "2")
    monkeypatch.setenv("VOLUME_SPIKE_RESEARCH_RATIO_THRESHOLD", "2.0")
    get_settings.cache_clear()

    db = _session_with_volume_spike()
    try:
        db.add(Stock(symbol="YYY", name="Y", sector="Tech", market_cap=None))
        base = date(2024, 7, 1)
        for i in range(5):
            d = base + timedelta(days=i)
            vol = 5000 if i == 4 else 1000
            db.add(
                PriceData(
                    stock_symbol="YYY",
                    date=d,
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=10.0,
                    volume=vol,
                )
            )
        db.commit()
        end_d = base + timedelta(days=4)
        backfill_volume_spikes(db, end_d, end_d, symbols=["YYY"], replace_range=False)
        backfill_volume_spikes(db, end_d, end_d, symbols=["YYY"], replace_range=True)
        assert db.query(VolumeSpikeEvent).filter(VolumeSpikeEvent.symbol == "YYY").count() == 1
    finally:
        get_settings.cache_clear()
        db.close()


@pytest.mark.integration
def test_backfill_invalid_range_raises() -> None:
    db = _session_with_volume_spike()
    try:
        with pytest.raises(ValueError, match="start_date"):
            backfill_volume_spikes(
                db, date(2024, 1, 5), date(2024, 1, 1), symbols=["ZZZ"], replace_range=False
            )
    finally:
        db.close()

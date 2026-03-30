"""S3 window sampling with DB-backed macro rows (deterministic, no Yahoo)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.vol_term_structure_observation import VolTermStructureObservation
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.services.daily_frequency_strategy_research import (
    _compute_s3_window_sample,
    bars_from_price_rows,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


@pytest.mark.unit
def test_compute_s3_window_sample_pools_regimes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    from backend.app.config import get_settings

    get_settings.cache_clear()

    db = _session()
    try:
        db.add(Stock(symbol="AAA", name="AAA", sector=None, market_cap=None))
        start = date(2024, 1, 2)
        for i in range(40):
            d = start + timedelta(days=i)
            c = 100.0 + 0.1 * i
            db.add(
                PriceData(
                    stock_symbol="AAA",
                    date=d,
                    open=c,
                    high=c + 0.2,
                    low=c - 0.2,
                    close=c,
                    volume=1_000_000,
                )
            )
        v0 = date(2023, 11, 1)
        for j in range(120):
            dd = v0 + timedelta(days=j)
            db.add(
                VolTermStructureObservation(
                    observation_date=dd,
                    vix_close=15.0 + (j % 10) * 0.1,
                    vix3m_close=16.0 + (j % 7) * 0.05,
                )
            )
        db.commit()

        rows = PriceDataRepository(db).list_for_stock("AAA")
        bars = bars_from_price_rows(rows)
        sample = _compute_s3_window_sample(
            db,
            bars,
            horizons=(1,),
            since=start + timedelta(days=15),
            until=start + timedelta(days=35),
        )
        assert sample is not None
        assert sum(sample.counts.values()) >= 1
        assert len(sample.baseline_returns["1"]) >= 1
    finally:
        db.close()
        get_settings.cache_clear()

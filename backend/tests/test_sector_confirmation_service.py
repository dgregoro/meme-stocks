"""Unit tests for sector ETF confirmation gate."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.price_data import PriceData
from backend.app.services.sector_confirmation_service import (
    SectorConfirmationParams,
    evaluate_sector_confirmation,
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


def _bar(session: Session, symbol: str, d: date, close: float) -> None:
    session.add(
        PriceData(
            stock_symbol=symbol,
            date=d,
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=1_000_000,
        )
    )


@pytest.mark.unit
def test_sector_ma_above_passes_when_close_above_ma() -> None:
    db = _session()
    try:
        repo = PriceDataRepository(db)
        d0, d1, d2 = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)
        for d, c in [(d0, 100.0), (d1, 100.0)]:
            _bar(db, "SMH", d, c)
        _bar(db, "SMH", d2, 105.0)
        db.commit()

        params = SectorConfirmationParams(
            enabled=True,
            sector_etf_symbol="SMH",
            sector_trend_method="ma_above",
            sector_trend_window=2,
            minimum_sector_return_pct=0.0,
            require_positive_trend=True,
        )
        ok, snap = evaluate_sector_confirmation(repo, "NVDA", d2, params)
        assert ok is True
        assert snap["sector_etf_symbol"] == "SMH"
        assert snap["sector_close"] == 105.0
        assert snap["sector_ma"] == 100.0
    finally:
        db.close()


@pytest.mark.unit
def test_sector_ma_above_fails_when_close_below_ma() -> None:
    db = _session()
    try:
        repo = PriceDataRepository(db)
        d0, d1, d2 = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)
        for d, c in [(d0, 100.0), (d1, 100.0)]:
            _bar(db, "SMH", d, c)
        _bar(db, "SMH", d2, 99.0)
        db.commit()

        params = SectorConfirmationParams(
            enabled=True,
            sector_etf_symbol="SMH",
            sector_trend_method="ma_above",
            sector_trend_window=2,
            minimum_sector_return_pct=0.0,
            require_positive_trend=True,
        )
        ok, snap = evaluate_sector_confirmation(repo, "NVDA", d2, params)
        assert ok is False
        assert snap.get("sector_skip_reason") == "sector_trend_not_met"
    finally:
        db.close()


@pytest.mark.unit
def test_sector_disabled_always_passes() -> None:
    db = _session()
    try:
        repo = PriceDataRepository(db)
        params = SectorConfirmationParams(
            enabled=False,
            sector_etf_symbol="SMH",
            sector_trend_method="ma_above",
            sector_trend_window=2,
            minimum_sector_return_pct=0.0,
            require_positive_trend=True,
        )
        ok, snap = evaluate_sector_confirmation(repo, "NVDA", date(2026, 1, 1), params)
        assert ok is True
        assert snap == {}
    finally:
        db.close()

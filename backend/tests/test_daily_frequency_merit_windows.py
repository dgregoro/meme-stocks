"""Unit tests for merit rolling window helpers (calendar vs trading union)."""

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
from backend.app.services.daily_frequency_strategy_research import (
    _load_union_trading_days,
    _merit_rolling_windows,
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
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory()


def _bar(symbol: str, d: date, close: float) -> PriceData:
    return PriceData(
        stock_symbol=symbol,
        date=d,
        open=close,
        high=close + 0.1,
        low=close - 0.1,
        close=close,
        volume=1_000_000,
    )


@pytest.mark.unit
def test_merit_rolling_windows_single_split() -> None:
    db = _session()
    try:
        ev_s, ev_e = date(2024, 1, 2), date(2024, 6, 1)
        wins, mode = _merit_rolling_windows(
            db,
            ev_s,
            ev_e,
            n_splits=1,
            split_mode="calendar",
            trading_calendar_symbols=["SPY"],
        )
        assert wins == [(ev_s, ev_e)]
        assert mode == "calendar"
    finally:
        db.close()


@pytest.mark.unit
def test_merit_rolling_windows_calendar_multi() -> None:
    db = _session()
    try:
        wins, mode = _merit_rolling_windows(
            db,
            date(2024, 1, 1),
            date(2024, 1, 21),
            n_splits=3,
            split_mode="calendar",
            trading_calendar_symbols=[],
        )
        assert len(wins) == 3
        assert mode == "calendar"
    finally:
        db.close()


@pytest.mark.unit
def test_merit_rolling_windows_trading_fallback_empty_union() -> None:
    db = _session()
    try:
        wins, mode = _merit_rolling_windows(
            db,
            date(2024, 1, 1),
            date(2024, 1, 10),
            n_splits=2,
            split_mode="trading",
            trading_calendar_symbols=["SPY"],
        )
        assert len(wins) == 2
        assert "fallback" in mode
    finally:
        db.close()


@pytest.mark.unit
def test_merit_rolling_windows_trading_uses_union_days() -> None:
    db = _session()
    try:
        db.add(Stock(symbol="AAA", name="A", sector=None, market_cap=None))
        db.add(Stock(symbol="BBB", name="B", sector=None, market_cap=None))
        d0 = date(2024, 1, 2)
        for i in range(10):
            db.add(_bar("AAA", d0 + timedelta(days=i), 100.0 + i))
        for i in range(10):
            db.add(_bar("BBB", d0 + timedelta(days=i), 50.0 + i))
        db.commit()

        wins, mode = _merit_rolling_windows(
            db,
            d0,
            d0 + timedelta(days=9),
            n_splits=2,
            split_mode="trading",
            trading_calendar_symbols=["AAA", "BBB"],
        )
        assert mode == "trading"
        assert len(wins) == 2
    finally:
        db.close()


@pytest.mark.unit
def test_load_union_trading_days_filters_range() -> None:
    db = _session()
    try:
        db.add(Stock(symbol="ZZ", name="Z", sector=None, market_cap=None))
        db.add(_bar("ZZ", date(2024, 1, 1), 1.0))
        db.add(_bar("ZZ", date(2024, 2, 1), 2.0))
        db.add(_bar("ZZ", date(2024, 4, 1), 3.0))
        db.commit()

        days = _load_union_trading_days(db, ["ZZ"], date(2024, 1, 15), date(2024, 3, 1))
        assert days == [date(2024, 2, 1)]
    finally:
        db.close()

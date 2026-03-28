"""Tests for market regime filter (014)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.regime_filter_service import RegimeFilterParams, evaluate_regime_filter


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _bar(session: Session, symbol: str, d: date, c: float) -> None:
    session.add(
        PriceData(
            stock_symbol=symbol,
            date=d,
            open=c,
            high=c * 1.01,
            low=c * 0.99,
            close=c,
            volume=1,
        )
    )


def _params(
    enabled: bool = True,
    regime_benchmark_symbol: str = "SPY",
    market_trend_window: int = 2,
    require_market_uptrend: bool = True,
    volatility_window: int = 2,
    volatility_threshold: float = 0.05,
    require_low_volatility: bool = False,
    regime_sector_strength_required: bool = False,
) -> RegimeFilterParams:
    return RegimeFilterParams(
        enabled=enabled,
        regime_benchmark_symbol=regime_benchmark_symbol,
        market_trend_window=market_trend_window,
        require_market_uptrend=require_market_uptrend,
        volatility_window=volatility_window,
        volatility_threshold=volatility_threshold,
        require_low_volatility=require_low_volatility,
        regime_sector_strength_required=regime_sector_strength_required,
    )


@pytest.mark.unit
def test_regime_disabled_passes(session: Session) -> None:
    session.add(Stock(symbol="SPY", name="s", sector=None, market_cap=None))
    session.commit()
    ok, snap = evaluate_regime_filter(
        PriceDataRepository(session),
        date(2026, 1, 7),
        _params(enabled=False),
    )
    assert ok is True
    assert snap == {}


@pytest.mark.unit
def test_uptrend_fail_when_close_below_ma(session: Session) -> None:
    session.add(Stock(symbol="SPY", name="s", sector=None, market_cap=None))
    session.commit()
    d0 = date(2026, 1, 5)
    d1 = date(2026, 1, 6)
    d2 = date(2026, 1, 7)
    _bar(session, "SPY", d0, 100.0)
    _bar(session, "SPY", d1, 100.0)
    _bar(session, "SPY", d2, 90.0)
    session.commit()
    repo = PriceDataRepository(session)
    ok, snap = evaluate_regime_filter(repo, d2, _params())
    assert ok is False
    assert snap.get("regime_benchmark_ma") == pytest.approx(100.0)
    assert snap.get("regime_market_uptrend_passed") is False


@pytest.mark.unit
def test_sector_strength_required_fails_when_sector_not_passed(session: Session) -> None:
    session.add(Stock(symbol="SPY", name="s", sector=None, market_cap=None))
    session.commit()
    d0 = date(2026, 1, 5)
    d1 = date(2026, 1, 6)
    d2 = date(2026, 1, 7)
    for d in (d0, d1, d2):
        _bar(session, "SPY", d, 102.0)
    session.commit()
    ok, snap = evaluate_regime_filter(
        PriceDataRepository(session),
        d2,
        _params(regime_sector_strength_required=True),
        sector_confirmation_passed=False,
    )
    assert ok is False
    assert snap.get("regime_skip_reason") == "sector_strength_required_not_met"


@pytest.mark.unit
def test_low_volatility_rejects_high_std(session: Session) -> None:
    session.add(Stock(symbol="SPY", name="s", sector=None, market_cap=None))
    session.commit()
    base = date(2026, 1, 5)
    # Wide swings -> high std of returns
    for i, c in enumerate([100.0, 110.0, 80.0]):
        _bar(session, "SPY", base + timedelta(days=i), c)
    session.commit()
    d2 = base + timedelta(days=2)
    ok, snap = evaluate_regime_filter(
        PriceDataRepository(session),
        d2,
        _params(require_market_uptrend=False, require_low_volatility=True, volatility_threshold=0.01),
    )
    assert ok is False
    assert snap.get("regime_low_volatility_passed") is False

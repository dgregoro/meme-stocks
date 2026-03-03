"""Tests for forward-return label computation and storage."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import price_data  # noqa: F401
from backend.app.models import price_labels  # noqa: F401
from backend.app.models import reddit_post  # noqa: F401 - RedditSymbolMention backref
from backend.app.models import reddit_symbol_mention  # noqa: F401 - Stock relationship
from backend.app.models import stock  # noqa: F401
from backend.app.services.label_service import compute_and_store_forward_returns


def _make_price(symbol: str, d: date, close: float, volume: int = 1000) -> Any:
    from backend.app.models.price_data import PriceData

    return PriceData(
        stock_symbol=symbol,
        date=d,
        open=close - 0.5,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=volume,
    )


@pytest.mark.unit
def test_fwd_return_5d_computed_correctly() -> None:
    """With trading days (Mon–Fri, skip weekend), h=5 uses 5th next session, not calendar offset."""
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.price_label_repo import PriceLabelRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        stock_repo.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
        db.flush()

        # Trading days only: Mon 2, Tue 3, Wed 4, Thu 5, Fri 6, Mon 9, Tue 10, Wed 11
        # (weekend 7–8 skipped, hole proves calendar-day logic would fail)
        dates = [
            date(2026, 2, 2),
            date(2026, 2, 3),
            date(2026, 2, 4),
            date(2026, 2, 5),
            date(2026, 2, 6),
            date(2026, 2, 9),
            date(2026, 2, 10),
            date(2026, 2, 11),
        ]
        # Close prices: 100, 101, 102, 103, 104, 105, 106, 107
        price_repo = PriceDataRepository(db)
        for i, d in enumerate(dates):
            price_repo.add(_make_price("GME", d, 100.0 + i))
        db.commit()

        stats = compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 5), horizons=[5])
        db.commit()

        assert int(stats["rows_upserted"]) >= 1
        assert stats["symbols_seen"] == 1

        label_repo = PriceLabelRepository(db)
        # D=2026-02-02, 5th next trading day = 2026-02-09 (indices 0->5)
        label = label_repo.get("GME", date(2026, 2, 2), 5)
        assert label is not None
        assert abs(label.fwd_return - ((105.0 / 100.0) - 1.0)) < 1e-9
        # D=2026-02-04, 5th next trading day = 2026-02-11 (indices 2->7)
        label2 = label_repo.get("GME", date(2026, 2, 4), 5)
        assert label2 is not None
        assert abs(label2.fwd_return - ((107.0 / 102.0) - 1.0)) < 1e-9
    finally:
        db.close()


@pytest.mark.unit
def test_missing_close_d_plus_h_no_label() -> None:
    """When h-th next trading day does not exist in PriceData, no label row is created."""
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.price_label_repo import PriceLabelRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        stock_repo.add(Stock(symbol="AMC", name="AMC", sector=None, market_cap=None))
        db.flush()

        # Only 2 trading days: 2026-02-02 and 2026-02-03; no 5th next session
        price_repo = PriceDataRepository(db)
        price_repo.add(_make_price("AMC", date(2026, 2, 2), 10.0))
        price_repo.add(_make_price("AMC", date(2026, 2, 3), 10.5))
        db.commit()

        compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 3), horizons=[5])
        db.commit()

        label_repo = PriceLabelRepository(db)
        label = label_repo.get("AMC", date(2026, 2, 2), 5)
        assert label is None

        label2 = label_repo.get("AMC", date(2026, 2, 3), 5)
        assert label2 is None
    finally:
        db.close()


@pytest.mark.unit
def test_horizon_uses_trading_days_not_calendar() -> None:
    """Horizon=1 uses next trading session (Fri->Mon), not calendar day (Fri->Sat)."""
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.price_label_repo import PriceLabelRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        stock_repo.add(Stock(symbol="XYZ", name="Test", sector=None, market_cap=None))
        db.flush()

        # Fri 2026-02-06, Mon 2026-02-09 (weekend 7-8 has no data)
        price_repo = PriceDataRepository(db)
        price_repo.add(_make_price("XYZ", date(2026, 2, 6), 100.0))
        price_repo.add(_make_price("XYZ", date(2026, 2, 9), 102.0))
        db.commit()

        compute_and_store_forward_returns(db, date(2026, 2, 6), date(2026, 2, 6), horizons=[1])
        db.commit()

        label_repo = PriceLabelRepository(db)
        label = label_repo.get("XYZ", date(2026, 2, 6), 1)
        assert label is not None
        # 1 trading session: Fri->Mon, fwd_return = 102/100 - 1 = 0.02
        assert abs(label.fwd_return - 0.02) < 1e-9
    finally:
        db.close()

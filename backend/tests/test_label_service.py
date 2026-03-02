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
    """With 7 consecutive trading days, fwd_return for h=5 is (close[D+5]/close[D]) - 1."""
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.price_label_repo import PriceLabelRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.price_data import PriceData
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        stock_repo.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
        db.flush()

        # 7 consecutive days: 2026-02-02 .. 2026-02-10 (Mon–Fri, Mon–Tue)
        dates = [
            date(2026, 2, 2),
            date(2026, 2, 3),
            date(2026, 2, 4),
            date(2026, 2, 5),
            date(2026, 2, 6),
            date(2026, 2, 9),  # Mon
            date(2026, 2, 10),
        ]
        # Close prices: 100, 101, 102, 103, 104, 105, 106
        price_repo = PriceDataRepository(db)
        for i, d in enumerate(dates):
            price_repo.add(_make_price("GME", d, 100.0 + i))
        db.commit()

        stats = compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 5), horizons=[5])
        db.commit()

        assert int(stats["rows_upserted"]) >= 1
        assert stats["symbols_seen"] == 1

        label_repo = PriceLabelRepository(db)
        # D=2026-02-02, D+5=2026-02-07 (Sat) - no data, skip
        # D=2026-02-03, D+5=2026-02-08 (Sun) - no data, skip
        # D=2026-02-04, D+5=2026-02-09 - close[2026-02-04]=102, close[2026-02-09]=105
        #   fwd_return = 105/102 - 1 = 0.02941...
        label = label_repo.get("GME", date(2026, 2, 4), 5)
        assert label is not None
        expected = (105.0 / 102.0) - 1.0
        assert abs(label.fwd_return - expected) < 1e-9
    finally:
        db.close()


@pytest.mark.unit
def test_missing_close_d_plus_h_no_label() -> None:
    """When close[D+h] does not exist in PriceData, no label row is created."""
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

        # Only D=2026-02-02 and D=2026-02-03; no D+5 (2026-02-07)
        price_repo = PriceDataRepository(db)
        price_repo.add(_make_price("AMC", date(2026, 2, 2), 10.0))
        price_repo.add(_make_price("AMC", date(2026, 2, 3), 10.5))
        db.commit()

        compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 3), horizons=[5])
        db.commit()

        label_repo = PriceLabelRepository(db)
        label = label_repo.get("AMC", date(2026, 2, 2), 5)
        assert label is None

        # D=2026-02-03, D+5=2026-02-08 (Sunday) - also no data
        label2 = label_repo.get("AMC", date(2026, 2, 3), 5)
        assert label2 is None
    finally:
        db.close()

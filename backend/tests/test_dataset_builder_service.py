"""Tests for training dataset builder: join features + labels."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import price_data  # noqa: F401
from backend.app.models import price_labels  # noqa: F401
from backend.app.models import reddit_daily_feature  # noqa: F401
from backend.app.models import reddit_post  # noqa: F401 - RedditSymbolMention backref
from backend.app.models import reddit_symbol_mention  # noqa: F401 - Stock relationship
from backend.app.models import stock  # noqa: F401
from backend.app.services.dataset_builder_service import build_training_dataset
from backend.app.services.label_service import compute_and_store_forward_returns


def _make_price(symbol: str, d: date, close: float, volume: int = 1000):
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


@pytest.mark.integration
def test_build_training_dataset_join_features_and_labels() -> None:
    """One RedditDailyFeature for (GME, 2026-02-02), PriceData for 2026-02-02 and 2026-02-07.

    After label generation and dataset build for horizon=5, assert one row with correct
    label and feature fields.
    """
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.reddit_daily_feature_repo import RedditDailyFeatureRepository
    from backend.app.data.repositories.stock_repo import StockRepository
    from backend.app.models.reddit_daily_feature import RedditDailyFeature
    from backend.app.models.stock import Stock

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stock_repo = StockRepository(db)
        stock_repo.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
        db.flush()

        # RedditDailyFeature for GME on 2026-02-02
        feature_repo = RedditDailyFeatureRepository(db)
        feature_repo.upsert(
            RedditDailyFeature(
                symbol="GME",
                trading_day=date(2026, 2, 2),
                mention_count=10,
                unique_authors=5,
                total_upvotes=100,
                total_comments=20,
                upvote_weighted_mentions=2.5,
            )
        )
        db.flush()

        # PriceData: trading days Mon 2..Fri 6, Mon 9 (weekend omitted; horizon=5 uses 5th session)
        price_repo = PriceDataRepository(db)
        price_repo.add(_make_price("GME", date(2026, 2, 2), 100.0, 5000))
        price_repo.add(_make_price("GME", date(2026, 2, 3), 101.0, 5100))
        price_repo.add(_make_price("GME", date(2026, 2, 4), 102.0, 5200))
        price_repo.add(_make_price("GME", date(2026, 2, 5), 103.0, 5300))
        price_repo.add(_make_price("GME", date(2026, 2, 6), 104.0, 5400))
        price_repo.add(_make_price("GME", date(2026, 2, 9), 105.0, 6000))
        db.commit()

        # Generate labels
        compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 2), horizons=[5])
        db.commit()

        # Build dataset for horizon=5
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            out_path = f.name

        try:
            stats = build_training_dataset(
                db,
                date(2026, 2, 2),
                date(2026, 2, 2),
                horizon_days=5,
                output_path=out_path,
                format="csv",
            )
            assert stats["rows_written"] == 1

            with open(out_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            r = rows[0]
            assert r["symbol"] == "GME"
            assert r["trading_day"] == "2026-02-02"
            assert r["mention_count"] == "10"
            assert r["unique_authors"] == "5"
            assert r["total_upvotes"] == "100"
            assert r["total_comments"] == "20"
            assert r["upvote_weighted_mentions"] == "2.5"
            assert r["close"] == "100.0"
            assert r["volume"] == "5000"
            # fwd_return = 105/100 - 1 = 0.05
            assert abs(float(r["y_fwd_return_5"]) - 0.05) < 1e-9
            assert "metadata_path" in stats
            meta_path = stats["metadata_path"]
            assert os.path.exists(meta_path)
            with open(meta_path, encoding="utf-8") as mf:
                meta = json.load(mf)
            assert meta["start_day"] == "2026-02-02"
            assert meta["end_day"] == "2026-02-02"
            assert meta["horizon_days"] == 5
        finally:
            os.unlink(out_path)
            meta_path = out_path + ".meta.json"
            if os.path.exists(meta_path):
                os.unlink(meta_path)
    finally:
        db.close()

"""Tests for training dataset builder: join features + labels."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.data.database import Base
from backend.app.models import price_data  # noqa: F401
from backend.app.models import price_labels  # noqa: F401
from backend.app.models import stock  # noqa: F401
from backend.app.services.dataset_builder_service import _get_git_sha, build_training_dataset
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


@pytest.mark.unit
def test_get_git_sha_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "abc123f")
    with patch("shutil.which", return_value=None):
        assert _get_git_sha() == "abc123f"


@pytest.mark.integration
def test_build_training_dataset_join_features_and_labels() -> None:
    """Price labels + OHLCV; legacy Reddit columns are zeros."""
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
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

        price_repo = PriceDataRepository(db)
        price_repo.add(_make_price("GME", date(2026, 2, 2), 100.0, 5000))
        price_repo.add(_make_price("GME", date(2026, 2, 3), 101.0, 5100))
        price_repo.add(_make_price("GME", date(2026, 2, 4), 102.0, 5200))
        price_repo.add(_make_price("GME", date(2026, 2, 5), 103.0, 5300))
        price_repo.add(_make_price("GME", date(2026, 2, 6), 104.0, 5400))
        price_repo.add(_make_price("GME", date(2026, 2, 9), 105.0, 6000))
        db.commit()

        compute_and_store_forward_returns(db, date(2026, 2, 2), date(2026, 2, 2), horizons=[5])
        db.commit()

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
            assert r["mention_count"] == "0"
            assert r["unique_authors"] == "0"
            assert r["total_upvotes"] == "0"
            assert r["total_comments"] == "0"
            assert r["upvote_weighted_mentions"] == "0.0"
            assert r["close"] == "100.0"
            assert r["volume"] == "5000"
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

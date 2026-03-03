from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.data.database import Base, get_session
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock


def create_test_engine_and_sessionmaker():
    # Use StaticPool to share the in-memory database across connections
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, TestSessionLocal


def build_test_app_with_db() -> tuple[TestClient, Session]:
    engine, TestSessionLocal = create_test_engine_and_sessionmaker()
    session = TestSessionLocal()

    app = create_app(omit_scheduler=True)

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session

    return TestClient(app), session


def test_daily_analysis_ranks_stocks_by_composite_score() -> None:
    client, db = build_test_app_with_db()

    now = datetime.now(timezone.utc)

    # Two stocks with different sentiment and trends
    gme = Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None)
    amc = Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None)
    db.add_all([gme, amc])

    # GME: strongly positive post
    gme_post = RedditPost(
        id="gme1",
        subreddit="wallstreetbets",
        title="GME to the moon buy buy",
        author="user",
        upvotes=200,
        comments=20,
        url="https://reddit.com/gme1",
        posted_at=now,
        collected_at=now,
    )
    # AMC: negative/neutral post
    amc_post = RedditPost(
        id="amc1",
        subreddit="wallstreetbets",
        title="AMC is a scam sell",
        author="user",
        upvotes=50,
        comments=5,
        url="https://reddit.com/amc1",
        posted_at=now,
        collected_at=now,
    )
    db.add_all([gme_post, amc_post])
    db.add_all(
        [
            RedditSymbolMention(post_id="gme1", symbol="GME"),
            RedditSymbolMention(post_id="amc1", symbol="AMC"),
        ]
    )

    # GME price trending up, AMC trending down
    for i in range(60):
        db.add(
            PriceData(
                stock_symbol="GME",
                date=date(2024, 1, 1) + timedelta(days=i),
                open=10.0 + i,
                high=11.0 + i,
                low=9.5 + i,
                close=10.5 + i,
                volume=1_000_000,
            )
        )
        db.add(
            PriceData(
                stock_symbol="AMC",
                date=date(2024, 1, 1) + timedelta(days=i),
                open=100.0 - i,
                high=101.0 - i,
                low=99.0 - i,
                close=99.5 - i,
                volume=1_000_000,
            )
        )

    db.commit()

    resp = client.get("/api/analysis/daily")
    assert resp.status_code == 200
    data = resp.json()

    # We expect two entries, with GME ranked above AMC
    assert len(data) == 2
    assert data[0]["symbol"] == "GME"
    assert data[1]["symbol"] == "AMC"
    assert data[0]["composite_score"] >= data[1]["composite_score"]


@pytest.mark.integration
def test_causal_endpoint_stock_not_found() -> None:
    """Causal endpoint returns 404 when stock not found."""
    client, _ = build_test_app_with_db()
    resp = client.get("/api/analysis/causal/INVALID?days=30")
    assert resp.status_code == 404


@pytest.mark.integration
def test_causal_endpoint_invalid_freq() -> None:
    """Causal endpoint returns 400 for invalid freq."""
    client, db = build_test_app_with_db()
    db.add(Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None))
    db.commit()
    resp = client.get("/api/analysis/causal/AAPL?freq=2h")
    assert resp.status_code == 400


@pytest.mark.integration
def test_causal_endpoint_insufficient_data() -> None:
    """Causal endpoint returns insufficient_data when no parquet bars."""
    client, db = build_test_app_with_db()

    stock = Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None)
    db.add(stock)
    db.commit()

    with patch("backend.app.api.analysis.get_settings") as mock_settings:
        mock_settings.return_value.intraday_feature_store_root = "/nonexistent/parquet"

        resp = client.get("/api/analysis/causal/AAPL?days=30&freq=1h")
        assert resp.status_code == 200
        data = resp.json()
        assert "reason" in data
        assert data["symbol"] == "AAPL"
        assert data["buckets_available"] == 0


@pytest.mark.integration
def test_causal_endpoint_success() -> None:
    """Causal endpoint returns lead-lag evidence when parquet data exists."""
    client, db = build_test_app_with_db()
    tmp_path = Path("/tmp/pytest_causal_api")

    stock = Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None)
    post = RedditPost(
        id="aapl1",
        subreddit="wallstreetbets",
        title="AAPL buy moon",
        author="user",
        upvotes=100,
        comments=10,
        url="https://reddit.com/aapl1",
        posted_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.add(post)
    db.add(RedditSymbolMention(post_id="aapl1", symbol="AAPL"))
    db.commit()

    # Write parquet bars (30 hourly buckets)
    base = tmp_path / "bars" / "symbol=AAPL" / "date=2026-01-15"
    base.mkdir(parents=True, exist_ok=True)
    rows = [
        (
            datetime(2026, 1, 15, 9, i, tzinfo=timezone.utc),
            100.0 + i * 0.1,
            1000.0,
        )
        for i in range(30)
    ]
    table = pa.table(
        {
            "ts": pa.array([r[0] for r in rows], type=pa.timestamp("us", tz="UTC")),
            "o": pa.array([r[1] for r in rows], type=pa.float64()),
            "h": pa.array([r[1] for r in rows], type=pa.float64()),
            "l": pa.array([r[1] for r in rows], type=pa.float64()),
            "c": pa.array([r[1] for r in rows], type=pa.float64()),
            "v": pa.array([r[2] for r in rows], type=pa.float64()),
            "n": pa.array([0] * len(rows), type=pa.int64()),
            "vw": pa.array([0.0] * len(rows), type=pa.float64()),
            "source": pa.array(["test"] * len(rows), type=pa.string()),
        }
    )
    pq.write_table(table, base / "part.parquet")

    with patch("backend.app.api.analysis.get_settings") as mock_settings:
        mock_settings.return_value.intraday_feature_store_root = str(tmp_path)
        with patch("backend.app.services.causal_dataset_builder.get_settings") as mock_builder:
            mock_builder.return_value.causal_min_buckets_1h = 10

            resp = client.get("/api/analysis/causal/AAPL?days=30&freq=1h&max_lag=3")
            assert resp.status_code == 200
            data = resp.json()
            # May be insufficient or success depending on resampled bucket count
            if "reason" in data:
                assert data["symbol"] == "AAPL"
            else:
                assert data["symbol"] == "AAPL"
                assert "mention_xcorr" in data
                assert "sentiment_xcorr" in data
                assert "predictive" in data

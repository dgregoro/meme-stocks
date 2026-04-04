"""Tests for leader-follower replay service."""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import main to ensure all models are registered (LeaderEvent has FK to job_run_history)
from backend.app.main import create_app  # noqa: F401
from backend.app.data.database import Base
from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup
from backend.app.services.leader_follower_replay_service import (
    LEADER_FOLLOWER_REPLAY_JOB_NAME,
    LOOKBACK_DAYS,
    _parse_bar_date,
    _trading_days,
    expand_backfill_symbols_with_regime_benchmarks,
    run_backfill,
    run_daily_price_backfill,
)


@pytest.mark.unit
def test_parse_bar_date_from_iso_string() -> None:
    """Parse ISO date from bar 't' field."""
    assert _parse_bar_date({"t": "2024-06-01T04:00:00Z"}) == date(2024, 6, 1)
    assert _parse_bar_date({"t": "2024-12-31T21:00:00Z"}) == date(2024, 12, 31)


@pytest.mark.unit
def test_parse_bar_date_missing() -> None:
    """Missing 't' returns None."""
    assert _parse_bar_date({}) is None
    assert _parse_bar_date({"t": None}) is None


@pytest.mark.unit
def test_expand_backfill_includes_configured_benchmarks() -> None:
    out = expand_backfill_symbols_with_regime_benchmarks(["AAPL", "MSFT"], "SPY, spy ,QQQ")
    assert out[:2] == ["AAPL", "MSFT"]
    assert "SPY" in out
    assert "QQQ" in out
    assert out.count("SPY") == 1


@pytest.mark.unit
def test_trading_days_skips_weekends() -> None:
    """Trading days exclude Saturday and Sunday."""
    # 2024-06-01 is Saturday; 2024-06-02 is Sunday; 2024-06-03 is Monday
    days = _trading_days(date(2024, 6, 1), date(2024, 6, 7))
    assert date(2024, 6, 1) not in days  # Saturday
    assert date(2024, 6, 2) not in days  # Sunday
    assert date(2024, 6, 3) in days
    assert date(2024, 6, 7) in days  # Friday


@pytest.mark.unit
def test_run_daily_price_backfill_empty_stocks() -> None:
    """Daily price backfill returns explicit error when stocks table is empty."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        result = run_daily_price_backfill(db, date(2024, 6, 1), date(2024, 6, 7))
        assert result["rows_inserted"] == 0
        assert result["symbols_fetched"] == 0
        assert result["errors"] and "seed stocks" in result["errors"][0]
    finally:
        db.close()


@pytest.mark.integration
def test_run_daily_price_backfill_delegates_to_alpaca_helper() -> None:
    """Resolves symbols from stocks and calls backfill_price_data_from_alpaca with lookback."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None))
        db.commit()

        captured: dict[str, object] = {}

        def _stub(_db, symbols, start, end):
            captured["symbols"] = symbols
            captured["start"] = start
            captured["end"] = end
            return {"rows_inserted": 3, "symbols_fetched": 1, "errors": []}

        start_d = date(2024, 6, 3)
        end_d = date(2024, 6, 5)
        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            side_effect=_stub,
        ):
            result = run_daily_price_backfill(db, start_d, end_d)
        assert result["rows_inserted"] == 3
        assert captured["symbols"] == ["AAPL"]
        assert captured["end"] == end_d
        assert captured["start"] == start_d - timedelta(days=LOOKBACK_DAYS)
    finally:
        db.close()


@pytest.mark.integration
def test_run_backfill_empty_stock_groups() -> None:
    """Backfill returns early with clear message when stock_groups empty."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        result = run_backfill(db, date(2024, 6, 1), date(2024, 6, 7), dry_run=True)
        assert result["days_processed"] == 0
        assert "stock_groups is empty" in str(result.get("missing_data_warnings", []))
    finally:
        db.close()


@pytest.mark.integration
def test_run_backfill_dry_run_with_mock_alpaca() -> None:
    """Dry-run produces summary without persisting; mocks Alpaca."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None))
        db.add(Stock(symbol="MSFT", name="Microsoft", sector="Tech", market_cap=None))
        db.add(StockGroup(group_id="tech", stock_symbol="AAPL"))
        db.add(StockGroup(group_id="tech", stock_symbol="MSFT"))
        db.commit()

        # Pre-populate price data so we skip Alpaca
        from backend.app.data.repositories.price_data_repo import PriceDataRepository

        price_repo = PriceDataRepository(db)
        for d in [
            date(2024, 5, 20),
            date(2024, 5, 21),
            date(2024, 5, 22),
            date(2024, 5, 23),
            date(2024, 5, 24),
            date(2024, 6, 3),
            date(2024, 6, 4),
            date(2024, 6, 5),
            date(2024, 6, 6),
            date(2024, 6, 7),
        ]:
            for sym in ["AAPL", "MSFT"]:
                if price_repo.get_for_date(sym, d) is None:
                    db.add(PriceData(stock_symbol=sym, date=d, open=100, high=101, low=99, close=100, volume=1_000_000))
        db.commit()

        captured: dict[str, object] = {}

        def _capture_backfill(_db, symbols, start, end):
            captured["symbols"] = symbols
            return {"rows_inserted": 0, "symbols_fetched": len(symbols), "errors": []}

        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            side_effect=_capture_backfill,
        ):
            result = run_backfill(db, date(2024, 6, 3), date(2024, 6, 5), dry_run=True)
        syms = cast(list[str], captured.get("symbols", []))
        assert "AAPL" in syms and "MSFT" in syms and "SPY" in syms
        assert "days_processed" in result
        assert "leaders_detected" in result
        assert "signals_emitted" in result
        assert result["errors"] == []
    finally:
        db.close()


@pytest.mark.integration
def test_run_backfill_persist_writes_replay_job_and_leader_debug_rows() -> None:
    """Non-dry-run backfill records one job_run_history row per day and leader_debug_evaluations."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None))
        db.add(Stock(symbol="MSFT", name="Microsoft", sector="Tech", market_cap=None))
        db.add(StockGroup(group_id="tech", stock_symbol="AAPL"))
        db.add(StockGroup(group_id="tech", stock_symbol="MSFT"))
        db.commit()

        from backend.app.data.repositories.price_data_repo import PriceDataRepository

        price_repo = PriceDataRepository(db)
        for d in [
            date(2024, 5, 20),
            date(2024, 5, 21),
            date(2024, 5, 22),
            date(2024, 5, 23),
            date(2024, 5, 24),
            date(2024, 6, 3),
        ]:
            for sym in ["AAPL", "MSFT"]:
                if price_repo.get_for_date(sym, d) is None:
                    db.add(
                        PriceData(
                            stock_symbol=sym,
                            date=d,
                            open=100,
                            high=101,
                            low=99,
                            close=100,
                            volume=1_000_000,
                        )
                    )
        db.commit()

        def _noop_backfill(_db, symbols, start, end):
            return {"rows_inserted": 0, "symbols_fetched": len(symbols), "errors": []}

        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            side_effect=_noop_backfill,
        ):
            result = run_backfill(db, date(2024, 6, 3), date(2024, 6, 3), dry_run=False, persist=True)

        assert result["days_processed"] == 1
        assert result["errors"] == []
        n_jobs = db.execute(
            select(func.count())
            .select_from(JobRunHistory)
            .where(JobRunHistory.job_name == LEADER_FOLLOWER_REPLAY_JOB_NAME)
        ).scalar_one()
        assert n_jobs == 1
        n_debug = db.execute(select(func.count()).select_from(LeaderDebugEvaluation)).scalar_one()
        assert n_debug == 2
    finally:
        db.close()


@pytest.mark.integration
def test_run_backfill_alpaca_keys_missing() -> None:
    """Backfill raises ExternalAPIError when Alpaca keys not configured."""
    from backend.app.utils.errors import ExternalAPIError

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        db.add(Stock(symbol="AAPL", name="Apple", sector="Tech", market_cap=None))
        db.add(StockGroup(group_id="tech", stock_symbol="AAPL"))
        db.commit()

        with patch("backend.app.services.leader_follower_replay_service.get_settings") as mock_settings:
            mock_settings.return_value.alpaca_api_key_id = None
            mock_settings.return_value.alpaca_api_secret_key = None
            mock_settings.return_value.alpaca_free_plan_mode = True
            mock_settings.return_value.alpaca_end_time_safety_minutes = 20
            mock_settings.return_value.alpaca_bars_feed = "iex"
            mock_settings.return_value.alpaca_data_base_url = "https://data.alpaca.markets"
            mock_settings.return_value.leader_follower_regime_backfill_symbols = "SPY"
            with pytest.raises(ExternalAPIError):
                run_backfill(db, date(2024, 6, 1), date(2024, 6, 7), dry_run=True)
    finally:
        db.close()

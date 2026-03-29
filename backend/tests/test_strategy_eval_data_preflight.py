"""Tests for strategy evaluation data preflight (spec 019)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings
import backend.app.cli.orm_imports  # noqa: F401 - full Base.metadata for create_all
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.daily_frequency_strategy_research import (
    assess_daily_strategy_symbol_data,
    daily_strategy_min_valid_bars,
)
from backend.app.services.strategy_eval_data_preflight import (
    run_strategy_eval_data_preflight,
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
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return TestSessionLocal()


def _add_daily_bars(db: Session, symbol: str, start: date, n_days: int) -> None:
    for i in range(n_days):
        d = start + timedelta(days=i)
        c = 100.0 + 0.1 * i
        db.add(
            PriceData(
                stock_symbol=symbol,
                date=d,
                open=c,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=1_000_000 + i * 100,
            )
        )


@pytest.mark.unit
def test_daily_strategy_min_valid_bars_s1_positive() -> None:
    assert daily_strategy_min_valid_bars("s1") >= 50


@pytest.mark.unit
def test_assess_missing_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    get_settings.cache_clear()
    db = _session()
    try:
        a = assess_daily_strategy_symbol_data(db, "NOPE", "s1", date(2024, 6, 1), date(2024, 8, 1))
        assert a.status == "missing_stock"
        assert a.valid_bar_count == 0
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_assess_insufficient_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="AAA", name="AAA", sector=None, market_cap=None))
        _add_daily_bars(db, "AAA", date(2024, 1, 2), n_days=5)
        db.commit()

        a = assess_daily_strategy_symbol_data(db, "AAA", "s2", date(2024, 1, 1), date(2024, 12, 31))
        assert a.status == "insufficient_history"
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_assess_ready_s2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="BBB", name="BBB", sector=None, market_cap=None))
        _add_daily_bars(db, "BBB", date(2024, 1, 2), n_days=40)
        db.commit()

        a = assess_daily_strategy_symbol_data(db, "BBB", "s2", date(2024, 2, 1), date(2024, 3, 1))
        assert a.status == "ready"
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_preflight_check_mode_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="CCC", name="CCC", sector=None, market_cap=None))
        _add_daily_bars(db, "CCC", date(2024, 1, 2), n_days=40)
        db.commit()

        with patch("backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca") as mock_bf:
            r = run_strategy_eval_data_preflight(
                db,
                ["CCC"],
                "s2",
                date(2024, 2, 1),
                date(2024, 3, 1),
                mode="check",
            )
        mock_bf.assert_not_called()
        assert r.all_ready is True
        assert r.errors == []
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_preflight_ensure_delegates_to_backfill(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure mode calls shared Alpaca backfill helper (mocked; no HTTP)."""
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="DDD", name="DDD", sector=None, market_cap=None))
        db.commit()

        def _fake_bf(db_sess: Session, symbols: list[str], _start: date, _end: date) -> dict:
            assert "DDD" in symbols
            _add_daily_bars(db_sess, "DDD", date(2024, 1, 2), n_days=40)
            db_sess.commit()
            return {"rows_inserted": 40, "symbols_fetched": 1, "errors": []}

        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            side_effect=_fake_bf,
        ) as mock_bf:
            r = run_strategy_eval_data_preflight(
                db,
                ["DDD"],
                "s2",
                date(2024, 2, 1),
                date(2024, 3, 1),
                mode="ensure",
            )
            mock_bf.assert_called_once()

        assert r.all_ready is True
        assert r.errors == []
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_preflight_ensure_backfill_errors_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="EEE", name="EEE", sector=None, market_cap=None))
        _add_daily_bars(db, "EEE", date(2024, 1, 2), n_days=3)
        db.commit()

        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            return_value={
                "rows_inserted": 0,
                "symbols_fetched": 0,
                "errors": ["Alpaca fetch for ['EEE']: rate limited"],
            },
        ):
            r = run_strategy_eval_data_preflight(
                db,
                ["EEE"],
                "s2",
                date(2024, 2, 1),
                date(2024, 3, 1),
                mode="ensure",
            )

        assert r.all_ready is False
        assert r.errors
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_preflight_ensure_all_stocks_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_ENSURE_DATA_MAX_SYMBOLS", "2")
    get_settings.cache_clear()
    db = _session()
    try:
        r = run_strategy_eval_data_preflight(
            db,
            ["A", "B", "C"],
            "s2",
            date(2024, 1, 1),
            date(2024, 2, 1),
            mode="ensure",
            all_stocks_ensure=True,
        )
        assert r.all_ready is False
        assert any("exceeds cap" in e for e in r.errors)
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_preflight_ensure_creates_stock_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:

        def _fake_bf(db_sess: Session, symbols: list[str], _start: date, _end: date) -> dict:
            _add_daily_bars(db_sess, "NEW1", date(2024, 1, 2), n_days=40)
            db_sess.commit()
            return {"rows_inserted": 40, "symbols_fetched": 1, "errors": []}

        with patch(
            "backend.app.services.leader_follower_replay_service.backfill_price_data_from_alpaca",
            side_effect=_fake_bf,
        ):
            r = run_strategy_eval_data_preflight(
                db,
                ["NEW1"],
                "s2",
                date(2024, 2, 1),
                date(2024, 3, 1),
                mode="ensure",
            )

        assert "stock_rows_created=1" in " ".join(r.actions_taken)
        assert r.all_ready is True
    finally:
        db.close()
        get_settings.cache_clear()

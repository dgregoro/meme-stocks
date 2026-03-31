"""Tests for run_s1/s2/s3_evaluation entrypoints (data sufficiency + happy path)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.vol_term_structure_observation import VolTermStructureObservation
from backend.app.services.daily_frequency_strategy_research import (
    run_s1_evaluation,
    run_s1_merit_report,
    run_s1_merit_rolling_report,
    run_s2_evaluation,
    run_s2_merit_report,
    run_s2_merit_rolling_report,
    run_s3_evaluation,
    run_s3_merit_report,
    run_s3_merit_rolling_report,
    run_strategy_merit_bundle,
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


def _seed_ohlcv(db: Session, symbol: str, start: date, n: int) -> None:
    for i in range(n):
        d = start + timedelta(days=i)
        c = 100.0 + 0.15 * i
        db.add(
            PriceData(
                stock_symbol=symbol,
                date=d,
                open=c,
                high=c + 0.3,
                low=c - 0.3,
                close=c,
                volume=800_000 + i * 500,
            )
        )


def _seed_price_and_vix_series(db: Session, symbol: str, *, n_price: int = 50) -> date:
    start = date(2024, 1, 2)
    db.add(Stock(symbol=symbol, name=symbol, sector=None, market_cap=None))
    _seed_ohlcv(db, symbol, start, n_price)
    v0 = date(2023, 11, 1)
    for j in range(120):
        dd = v0 + timedelta(days=j)
        db.add(
            VolTermStructureObservation(
                observation_date=dd,
                vix_close=15.0 + (j % 10) * 0.1,
                vix3m_close=16.0 + (j % 7) * 0.05,
            )
        )
    return start


@pytest.mark.unit
def test_run_s1_evaluation_insufficient_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="X1", name="X", sector=None, market_cap=None))
        _seed_ohlcv(db, "X1", date(2024, 1, 2), 5)
        db.commit()
        out = run_s1_evaluation(db, "X1", date(2024, 1, 1), date(2024, 12, 31))
        assert out.get("error") == "insufficient_price_data"
        assert "hint" in out
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s1_evaluation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="S1OK", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "S1OK", date(2024, 1, 2), 80)
        db.commit()
        out = run_s1_evaluation(db, "S1OK", date(2024, 2, 1), date(2024, 4, 1))
        assert out.get("error") is None
        assert out["strategy"] == "S1_volume_realized_vol_mismatch"
        assert set(out["by_regime"].keys()) >= {"hv_lv", "lv_hv", "neutral"}
        assert sum(out["counts"].values()) > 0
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s2_evaluation_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="S2X", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "S2X", date(2024, 1, 2), 5)
        db.commit()
        out = run_s2_evaluation(db, "S2X", None, None)
        assert out.get("error") == "insufficient_price_data"
        assert "by_bucket" in out
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s2_evaluation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="S2OK", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "S2OK", date(2024, 1, 2), 50)
        db.commit()
        out = run_s2_evaluation(db, "S2OK", date(2024, 2, 1), date(2024, 3, 31))
        assert out.get("error") is None
        assert out["strategy"] == "S2_gap_ecology"
        assert any(out["counts"].values())
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s3_evaluation_insufficient_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "5")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="S3X", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "S3X", date(2024, 1, 2), 5)
        db.commit()
        out = run_s3_evaluation(db, "S3X", None, None)
        assert out.get("error") == "insufficient_price_data"
        assert "by_regime" in out
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s3_evaluation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    get_settings.cache_clear()
    db = _session()
    try:
        start = _seed_price_and_vix_series(db, "S3OK", n_price=45)
        db.commit()
        out = run_s3_evaluation(db, "S3OK", start + timedelta(days=10), start + timedelta(days=35))
        assert out.get("error") is None
        assert out["strategy"] == "S3_vol_term_structure"
        assert out["params"]["s3_regime_n_buckets"] >= 2
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s1_merit_report_pooled_two_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        for sym in ("M1", "M2"):
            db.add(Stock(symbol=sym, name=sym, sector=None, market_cap=None))
            _seed_ohlcv(db, sym, date(2024, 1, 2), 95)
        db.commit()
        rep = run_s1_merit_report(db, ["M1", "M2"], date(2024, 2, 1), date(2024, 4, 30))
        assert rep["kind"] == "s1_merit_report"
        assert isinstance(rep["checklist"]["pass"], bool)
        assert "baseline_metrics" in rep
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s1_merit_rolling_calendar_splits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="R1", name="R", sector=None, market_cap=None))
        _seed_ohlcv(db, "R1", date(2024, 1, 2), 100)
        db.commit()
        roll = run_s1_merit_rolling_report(
            db,
            ["R1"],
            date(2024, 2, 1),
            date(2024, 5, 15),
            n_splits=2,
            split_mode="calendar",
        )
        assert roll["kind"] == "s1_merit_report_rolling"
        assert len(roll["splits"]) == 2
        assert "rollup" in roll
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s2_merit_report_pooled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="G2", name="G", sector=None, market_cap=None))
        _seed_ohlcv(db, "G2", date(2024, 1, 2), 60)
        db.commit()
        rep = run_s2_merit_report(db, ["G2"], date(2024, 2, 1), date(2024, 3, 31))
        assert rep["kind"] == "s2_merit_report"
        assert "by_bucket" in rep
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_strategy_merit_bundle_s1_includes_rolling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="B1", name="B", sector=None, market_cap=None))
        _seed_ohlcv(db, "B1", date(2024, 1, 2), 100)
        db.commit()
        bundle = run_strategy_merit_bundle(
            db,
            "s1",
            ["B1"],
            date(2024, 2, 1),
            date(2024, 5, 20),
            rolling_splits=2,
            split_mode="calendar",
        )
        assert bundle["kind"] == "strategy_merit_bundle"
        assert bundle["rolling"] is not None
        assert "summary" in bundle
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s2_merit_rolling_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="S2R", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "S2R", date(2024, 1, 2), 70)
        db.commit()
        roll = run_s2_merit_rolling_report(
            db,
            ["S2R"],
            date(2024, 2, 1),
            date(2024, 4, 20),
            n_splits=2,
            split_mode="calendar",
        )
        assert roll["kind"] == "s2_merit_report_rolling"
        assert len(roll["splits"]) == 2
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s3_merit_report_pooled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        start = _seed_price_and_vix_series(db, "MER3", n_price=55)
        db.commit()
        rep = run_s3_merit_report(db, ["MER3"], start + timedelta(days=5), start + timedelta(days=45))
        assert rep["kind"] == "s3_merit_report"
        assert "by_regime" in rep
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_s3_merit_rolling_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    get_settings.cache_clear()
    db = _session()
    try:
        _ = _seed_price_and_vix_series(db, "M3R", n_price=80)
        db.commit()
        roll = run_s3_merit_rolling_report(
            db,
            ["M3R"],
            date(2024, 2, 1),
            date(2024, 4, 25),
            n_splits=2,
            split_mode="calendar",
        )
        assert roll["kind"] == "s3_merit_report_rolling"
        assert len(roll["splits"]) == 2
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_strategy_merit_bundle_s2_and_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "20")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    get_settings.cache_clear()
    db = _session()
    try:
        db.add(Stock(symbol="SB2", name="S", sector=None, market_cap=None))
        _seed_ohlcv(db, "SB2", date(2024, 1, 2), 75)
        _ = _seed_price_and_vix_series(db, "SB3", n_price=75)
        db.commit()

        b2 = run_strategy_merit_bundle(
            db,
            "s2",
            ["SB2"],
            date(2024, 2, 1),
            date(2024, 4, 15),
            rolling_splits=2,
            split_mode="calendar",
        )
        assert b2["rolling"] is not None

        b3 = run_strategy_merit_bundle(
            db,
            "s3",
            ["SB3"],
            date(2024, 2, 1),
            date(2024, 4, 15),
            rolling_splits=2,
            split_mode="calendar",
        )
        assert b3["rolling"] is not None
    finally:
        db.close()
        get_settings.cache_clear()

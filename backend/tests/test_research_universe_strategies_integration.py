"""Integration: S1–S6 daily strategy eval + merit on the repo's 100-symbol research universe.

Uses in-memory SQLite and synthetic OHLCV + VIX/VIX3M so CI does not depend on ``data/app.db``
or Alpaca. S7 uses ``research rule-discovery`` (feature matrix + gated search), not
``evaluate daily-strategy`` — excluded from this S1–S6 integration test.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

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
    run_s2_evaluation,
    run_s2_merit_report,
    run_s3_evaluation,
    run_s3_merit_report,
    run_s4_evaluation,
    run_s4_merit_report,
    run_s5_evaluation,
    run_s5_merit_report,
    run_s6_evaluation,
    run_s6_merit_report,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_universe_symbols() -> list[str]:
    path = _repo_root() / "data/research/universes/s1_merit_100_under50b.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    symbols = [ln.strip().upper() for ln in lines if ln.strip()]
    if len(symbols) != 100:
        raise AssertionError(f"expected 100 symbols in {path}, got {len(symbols)}")
    return symbols


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


def _seed_equity_panel(db: Session, symbols: list[str], start: date, n_calendar_days: int) -> None:
    """Aligned calendar panel (same pattern as tests for S5 cross-section)."""
    for j, sym in enumerate(symbols):
        db.add(Stock(symbol=sym, name=sym, sector=None, market_cap=None))
        for i in range(n_calendar_days):
            d = start + timedelta(days=i)
            c = 100.0 + 0.12 * i + j * 0.04 * (i % 11)
            db.add(
                PriceData(
                    stock_symbol=sym,
                    date=d,
                    open=c,
                    high=c + 0.3,
                    low=c - 0.3,
                    close=c,
                    volume=800_000 + i * 400 + j * 1000,
                )
            )


def _seed_vix_series(db: Session, start: date, n_days: int) -> None:
    for j in range(n_days):
        dd = start + timedelta(days=j)
        db.add(
            VolTermStructureObservation(
                observation_date=dd,
                vix_close=15.0 + (j % 10) * 0.1,
                vix3m_close=16.0 + (j % 7) * 0.05,
            )
        )


def _patch_universe_eval_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink windows so 100-symbol merit stays fast; keep S5 panel minimum at 10."""
    monkeypatch.setenv("DAILY_STRATEGY_HORIZONS", "1")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_MIN_PRIOR_DAYS", "10")
    monkeypatch.setenv("DAILY_STRATEGY_REGIME_LOOKBACK_DAYS", "15")
    monkeypatch.setenv("DAILY_STRATEGY_REALIZED_VOL_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_VOLUME_Z_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_GAP_MA_WINDOW", "5")
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_MIN_EVENTS_PER_REGIME", "1")
    monkeypatch.setenv("S3_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S3_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S3_MACRO_BACKFILL_CALENDAR_BUFFER_DAYS", "60")
    monkeypatch.setenv("S3_FEATURE_MODE", "spread")
    monkeypatch.setenv("S5_MIN_SYMBOLS_CROSS_SECTION", "10")
    monkeypatch.setenv("S5_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S5_REGIME_N_BUCKETS", "4")
    monkeypatch.setenv("S5_LOAD_BUFFER_CALENDAR_DAYS", "80")
    monkeypatch.setenv("S6_BETA_WINDOW_DAYS", "5")
    monkeypatch.setenv("S6_ZSCORE_WINDOW_DAYS", "5")
    monkeypatch.setenv("S6_REGIME_MIN_HISTORY_DAYS", "5")
    monkeypatch.setenv("S6_REGIME_N_BUCKETS", "4")
    get_settings.cache_clear()


@pytest.mark.integration
def test_s1_through_s6_single_symbol_and_merit_100_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = _load_universe_symbols()
    _patch_universe_eval_env(monkeypatch)

    price_start = date(2024, 1, 2)
    n_price = 260
    vix_start = date(2023, 6, 1)
    n_vix = 450

    eval_start = date(2024, 4, 1)
    eval_end = date(2024, 9, 26)

    leg_a = symbols[0]
    leg_b = symbols[1]

    db = _session()
    try:
        _seed_equity_panel(db, symbols, price_start, n_price)
        _seed_vix_series(db, vix_start, n_vix)
        db.commit()

        o1 = run_s1_evaluation(db, leg_a, eval_start, eval_end)
        assert o1.get("error") is None
        o2 = run_s2_evaluation(db, leg_a, eval_start, eval_end)
        assert o2.get("error") is None
        o3 = run_s3_evaluation(db, leg_a, eval_start, eval_end)
        assert o3.get("error") is None
        o4 = run_s4_evaluation(db, leg_a, eval_start, eval_end)
        assert o4.get("error") is None
        o5 = run_s5_evaluation(
            db,
            leg_a,
            eval_start,
            eval_end,
            panel_universe=symbols,
        )
        assert o5.get("error") is None
        o6 = run_s6_evaluation(
            db,
            leg_a,
            eval_start,
            eval_end,
            pair_leg_b=leg_b,
        )
        assert o6.get("error") is None

        m1 = run_s1_merit_report(db, symbols, eval_start, eval_end)
        assert m1["kind"] == "s1_merit_report"
        m2 = run_s2_merit_report(db, symbols, eval_start, eval_end)
        assert m2["kind"] == "s2_merit_report"
        m3 = run_s3_merit_report(db, symbols, eval_start, eval_end)
        assert m3["kind"] == "s3_merit_report"
        m4 = run_s4_merit_report(db, symbols, eval_start, eval_end)
        assert m4["kind"] == "s4_merit_report"
        m5 = run_s5_merit_report(db, symbols, eval_start, eval_end)
        assert m5["kind"] == "s5_merit_report"
        m6 = run_s6_merit_report(db, symbols, eval_start, eval_end, leg_b=leg_b)
        assert m6["kind"] == "s6_merit_report"
    finally:
        db.close()
        get_settings.cache_clear()

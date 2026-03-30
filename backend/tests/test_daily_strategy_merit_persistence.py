"""Tests for persisting daily-strategy merit / bundle reports."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.config import get_settings
from backend.app.data.database import Base
from backend.app.data.repositories.daily_strategy_merit_run_repo import DailyStrategyMeritRunRepository
from backend.app.services.daily_strategy_merit_persistence import (
    build_merit_run_row,
    try_persist_merit_report,
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


@pytest.mark.unit
def test_build_merit_run_row_s1() -> None:
    rep = {
        "kind": "s1_merit_report",
        "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
        "symbols_requested": ["SPY"],
        "checklist": {"pass": True, "failures": []},
    }
    row = build_merit_run_row(rep)
    assert row.report_kind == "s1_merit_report"
    assert row.strategy_id == "s1"
    assert row.symbol_count == 1
    assert row.checklist_pass is True
    assert row.rolling_pass is None
    assert row.all_gates_pass is None


@pytest.mark.unit
def test_build_merit_run_row_s3() -> None:
    rep = {
        "kind": "s3_merit_report",
        "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
        "symbols_requested": ["SPY"],
        "checklist": {"pass": False, "failures": ["x"]},
    }
    row = build_merit_run_row(rep)
    assert row.strategy_id == "s3"
    assert row.checklist_pass is False


@pytest.mark.unit
def test_build_merit_run_row_bundle() -> None:
    rep = {
        "kind": "strategy_merit_bundle",
        "strategy": "s2",
        "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
        "symbols_requested": ["X"],
        "rolling_splits_configured": 3,
        "split_mode": "trading",
        "single_window": {"checklist": {"pass": True}},
        "rolling": None,
        "summary": {
            "single_window_checklist_pass": True,
            "rolling_rollup_pass": None,
            "all_automated_gates_pass": True,
        },
    }
    row = build_merit_run_row(rep)
    assert row.strategy_id == "s2"
    assert row.n_splits == 3
    assert row.split_mode == "trading"
    assert row.all_gates_pass is True


@pytest.mark.unit
def test_try_persist_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_PERSIST_RUNS", "false")
    get_settings.cache_clear()
    db = _session()
    try:
        rep = {
            "kind": "s1_merit_report",
            "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
            "symbols_requested": ["SPY"],
            "checklist": {"pass": True, "failures": []},
        }
        assert try_persist_merit_report(db, rep) is None
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_try_persist_skip_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_PERSIST_RUNS", "true")
    get_settings.cache_clear()
    db = _session()
    try:
        rep = {
            "kind": "s1_merit_report",
            "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
            "symbols_requested": ["SPY"],
            "checklist": {"pass": True, "failures": []},
        }
        assert try_persist_merit_report(db, rep, skip=True) is None
        assert DailyStrategyMeritRunRepository(db).list_recent(limit=10) == []
    finally:
        db.close()
        get_settings.cache_clear()


@pytest.mark.unit
def test_try_persist_inserts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_STRATEGY_MERIT_PERSIST_RUNS", "true")
    get_settings.cache_clear()
    db = _session()
    try:
        rep = {
            "kind": "s1_merit_report",
            "eval_window": {"start": "2024-01-01", "end": "2024-06-01"},
            "symbols_requested": ["SPY"],
            "checklist": {"pass": False, "failures": ["nope"]},
        }
        rid = try_persist_merit_report(db, rep)
        assert rid == 1
        loaded = DailyStrategyMeritRunRepository(db).get(1)
        assert loaded is not None
        assert loaded.checklist_pass is False
        roundtrip = json.loads(loaded.report_json)
        assert roundtrip["kind"] == "s1_merit_report"
    finally:
        db.close()
        get_settings.cache_clear()

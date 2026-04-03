"""Tests for S1–S7 suite orchestration (persist merit + S7)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.data.database import Base
from backend.app.services.research_strategy_suite import run_research_strategy_suite_and_persist


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
def test_suite_requires_two_symbols() -> None:
    db = _session()
    try:
        with pytest.raises(ValueError, match="at least two"):
            run_research_strategy_suite_and_persist(
                db,
                ["AAA"],
                date(2024, 1, 2),
                date(2024, 6, 1),
                leg_b="BBB",
                s7_train_end=date(2024, 3, 15),
                ack_s7_overfitting_risk=False,
            )
    finally:
        db.close()


@pytest.mark.unit
def test_suite_leg_b_must_be_in_symbols() -> None:
    db = _session()
    try:
        with pytest.raises(ValueError, match="leg_b"):
            run_research_strategy_suite_and_persist(
                db,
                ["AAA", "BBB"],
                date(2024, 1, 2),
                date(2024, 6, 1),
                leg_b="ZZZ",
                s7_train_end=date(2024, 3, 15),
                ack_s7_overfitting_risk=False,
            )
    finally:
        db.close()


@pytest.mark.unit
def test_suite_skips_s7_without_ack() -> None:
    db = _session()
    try:
        out = run_research_strategy_suite_and_persist(
            db,
            ["AAA", "BBB"],
            date(2024, 1, 2),
            date(2024, 6, 1),
            leg_b="BBB",
            s7_train_end=date(2024, 3, 15),
            no_persist=True,
            ack_s7_overfitting_risk=False,
        )
        assert out["s7"]["skipped"] is True
        assert out["merit_run_ids"]["s7"] is None
    finally:
        db.close()

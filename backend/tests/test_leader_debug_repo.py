"""Tests for LeaderDebugRepository."""

from __future__ import annotations

import json

import pytest

# Import main to ensure all models are registered (LeaderDebugEvaluation, job_run_history)
from backend.app.main import create_app  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.data.repositories.leader_debug_repo import LeaderDebugRepository


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


@pytest.fixture
def seeded_session(session: Session) -> Session:
    evals = [
        LeaderDebugEvaluation(
            job_run_id=1,
            stock_symbol="GME",
            return_pct=4.2,
            volume_ratio=1.4,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["below_return_threshold", "insufficient_volume"]),
        ),
        LeaderDebugEvaluation(
            job_run_id=1,
            stock_symbol="NVDA",
            return_pct=2.1,
            volume_ratio=0.9,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["below_return_threshold", "insufficient_volume"]),
        ),
        LeaderDebugEvaluation(
            job_run_id=1,
            stock_symbol="AMC",
            return_pct=None,
            volume_ratio=None,
            qualified_as_leader=False,
            rejection_reasons=json.dumps(["insufficient_bars"]),
        ),
        LeaderDebugEvaluation(
            job_run_id=1,
            stock_symbol="AAPL",
            return_pct=6.0,
            volume_ratio=2.0,
            qualified_as_leader=True,
            rejection_reasons=json.dumps([]),
        ),
    ]
    for e in evals:
        session.add(e)
    session.commit()
    return session


@pytest.mark.unit
def test_add_and_list_by_run_id(seeded_session: Session) -> None:
    repo = LeaderDebugRepository(seeded_session)
    rows = repo.list_by_run_id(1, limit=10)
    symbols = [r.stock_symbol for r in rows]
    assert symbols == ["AAPL", "AMC", "GME", "NVDA"]


@pytest.mark.unit
def test_list_near_misses_excludes_insufficient_bars(seeded_session: Session) -> None:
    repo = LeaderDebugRepository(seeded_session)
    rows = repo.list_near_misses_by_run_id(1, limit=10)
    symbols = [r.stock_symbol for r in rows]
    assert "AMC" not in symbols
    assert "AAPL" not in symbols  # qualified, not near-miss


@pytest.mark.unit
def test_list_near_misses_ordered_by_proximity(seeded_session: Session) -> None:
    repo = LeaderDebugRepository(seeded_session)
    rows = repo.list_near_misses_by_run_id(1, limit=10)
    symbols = [r.stock_symbol for r in rows]
    assert symbols == ["GME", "NVDA"]
    assert rows[0].return_pct == 4.2
    assert rows[1].return_pct == 2.1


@pytest.mark.unit
def test_list_by_run_id_empty(session: Session) -> None:
    repo = LeaderDebugRepository(session)
    assert list(repo.list_by_run_id(999)) == []


@pytest.mark.unit
def test_list_near_misses_empty(session: Session) -> None:
    repo = LeaderDebugRepository(session)
    assert list(repo.list_near_misses_by_run_id(999)) == []

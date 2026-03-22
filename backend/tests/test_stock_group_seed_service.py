"""Tests for stock group bootstrap seeding."""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup
from backend.app.services.stock_group_seed_service import run_bootstrap_seed


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def test_run_bootstrap_seed_inserts_groups(session: Session) -> None:
    """First run inserts stock-group memberships."""
    result = run_bootstrap_seed(session)
    session.commit()

    assert result["groups_inserted"] > 0
    repo = StockGroupRepository(session)
    assert repo.count_total() == result["groups_inserted"]


def test_run_bootstrap_seed_idempotent(session: Session) -> None:
    """Second run skips existing pairs (no duplicates)."""
    result1 = run_bootstrap_seed(session)
    session.commit()
    total_after_first = result1["groups_inserted"]

    result2 = run_bootstrap_seed(session)
    session.commit()

    assert result2["groups_inserted"] == 0
    assert result2["groups_skipped"] == total_after_first
    repo = StockGroupRepository(session)
    assert repo.count_total() == total_after_first


def test_run_bootstrap_seed_creates_missing_stocks(session: Session) -> None:
    """Seeding creates minimal stocks when missing (FK integrity)."""
    result = run_bootstrap_seed(session)
    session.commit()

    assert result["stocks_created"] >= 0  # May be 0 if stocks exist from other fixtures
    stock_repo = StockRepository(session)
    # At least meme group symbols should exist
    for sym in ["GME", "AMC", "BB"]:
        stock = stock_repo.get(sym)
        assert stock is not None
        assert stock.symbol == sym


def test_run_bootstrap_seed_does_not_wipe_existing(session: Session) -> None:
    """Pre-existing user-defined groups are preserved."""
    group_repo = StockGroupRepository(session)
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="CUSTOM", name="Custom", sector=None, market_cap=None))
    session.flush()
    group_repo.add(StockGroup(group_id="user_defined", stock_symbol="CUSTOM"))
    session.commit()
    before_count = group_repo.count_total()

    result = run_bootstrap_seed(session)
    session.commit()

    after_count = group_repo.count_total()
    assert after_count > before_count
    symbols = group_repo.get_symbols_in_group("user_defined")
    assert "CUSTOM" in symbols

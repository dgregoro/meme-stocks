"""Tests for stock group bootstrap seeding."""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine

# Ensure all models are registered (Stock has relationships to other models)
from backend.app.main import create_app  # noqa: F401

from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.stock_group_seed import BOOTSTRAP_GROUPS
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup
from backend.app.services.stock_group_seed_service import run_bootstrap_seed


def _create_stocks_for_bootstrap(session: Session) -> None:
    """Pre-create stocks so seed can add them to groups (seed skips symbols not in stocks)."""
    stock_repo = StockRepository(session)
    for symbols in BOOTSTRAP_GROUPS.values():
        for sym in symbols:
            if stock_repo.get(sym) is None:
                stock_repo.add(Stock(symbol=sym, name=f"{sym} (test)", sector=None, market_cap=None))
    session.flush()


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def test_run_bootstrap_seed_inserts_groups(session: Session) -> None:
    """First run inserts stock-group memberships when stocks exist."""
    _create_stocks_for_bootstrap(session)
    session.commit()

    result = run_bootstrap_seed(session)
    session.commit()

    assert result["groups_inserted"] > 0
    repo = StockGroupRepository(session)
    assert repo.count_total() == result["groups_inserted"]


def test_run_bootstrap_seed_idempotent(session: Session) -> None:
    """Second run skips existing pairs (no duplicates)."""
    _create_stocks_for_bootstrap(session)
    session.commit()

    result1 = run_bootstrap_seed(session)
    session.commit()
    total_after_first = result1["groups_inserted"]

    result2 = run_bootstrap_seed(session)
    session.commit()

    assert result2["groups_inserted"] == 0
    assert result2["groups_skipped"] == total_after_first
    repo = StockGroupRepository(session)
    assert repo.count_total() == total_after_first


def test_run_bootstrap_seed_skips_symbols_not_in_stocks(session: Session) -> None:
    """Seeding skips symbols not in stocks table (logs warning, reports in symbols_skipped)."""
    # No stocks created - seed should skip all and report in symbols_skipped
    result = run_bootstrap_seed(session)
    session.commit()

    assert result["groups_inserted"] == 0
    assert result["stocks_created"] == 0
    assert len(result["symbols_skipped"]) > 0


def test_run_bootstrap_seed_does_not_wipe_existing(session: Session) -> None:
    """Pre-existing user-defined groups are preserved."""
    group_repo = StockGroupRepository(session)
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="CUSTOM", name="Custom", sector=None, market_cap=None))
    session.flush()
    group_repo.add(StockGroup(group_id="user_defined", stock_symbol="CUSTOM"))
    session.commit()
    before_count = group_repo.count_total()

    _create_stocks_for_bootstrap(session)
    session.commit()
    run_bootstrap_seed(session)
    session.commit()

    after_count = group_repo.count_total()
    assert after_count > before_count
    symbols = group_repo.get_symbols_in_group("user_defined")
    assert "CUSTOM" in symbols

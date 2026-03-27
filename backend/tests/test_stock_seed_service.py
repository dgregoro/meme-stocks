"""Tests for stock bootstrap seeding."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from backend.app.main import create_app  # noqa: F401 - ensure all models registered
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.stock_group_seed import BOOTSTRAP_GROUPS
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.services.stock_seed_service import seed_stocks_for_bootstrap


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def test_seed_stocks_creates_all_symbols(session: Session) -> None:
    """First run creates stocks for all unique symbols in BOOTSTRAP_GROUPS."""
    result = seed_stocks_for_bootstrap(session)
    session.commit()

    all_symbols = set()
    for symbols in BOOTSTRAP_GROUPS.values():
        all_symbols.update(symbols)
    assert result["created"] == len(all_symbols)
    assert result["total"] == len(all_symbols)

    repo = StockRepository(session)
    for sym in all_symbols:
        stock = repo.get(sym)
        assert stock is not None
        assert stock.symbol == sym
        assert stock.name == sym


def test_seed_stocks_idempotent(session: Session) -> None:
    """Second run creates nothing; all already exist."""
    result1 = seed_stocks_for_bootstrap(session)
    session.commit()

    result2 = seed_stocks_for_bootstrap(session)
    session.commit()

    assert result1["created"] == result1["total"]
    assert result2["created"] == 0
    assert result2["total"] == result1["total"]

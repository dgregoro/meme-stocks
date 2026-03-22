"""Tests for StockGroupRepository extended methods."""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


@pytest.fixture
def seeded_session(session: Session) -> Session:
    session.add(Stock(symbol="GME", name="GameStop", sector=None, market_cap=None))
    session.add(Stock(symbol="AMC", name="AMC", sector=None, market_cap=None))
    session.flush()
    session.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.add(StockGroup(group_id="tech", stock_symbol="GME"))
    session.commit()
    return session


def test_count_total_empty(session: Session) -> None:
    repo = StockGroupRepository(session)
    assert repo.count_total() == 0


def test_count_total(seeded_session: Session) -> None:
    repo = StockGroupRepository(seeded_session)
    assert repo.count_total() == 3


def test_list_group_ids(seeded_session: Session) -> None:
    repo = StockGroupRepository(seeded_session)
    ids = repo.list_group_ids()
    assert ids == ["meme", "tech"]


def test_exists(seeded_session: Session) -> None:
    repo = StockGroupRepository(seeded_session)
    assert repo.exists("meme", "GME") is True
    assert repo.exists("meme", "AMC") is True
    assert repo.exists("meme", "TSLA") is False
    assert repo.exists("oil", "XOM") is False


def test_add_if_missing_inserts(seeded_session: Session) -> None:
    session = seeded_session
    session.add(Stock(symbol="NVDA", name="NVIDIA", sector=None, market_cap=None))
    session.flush()
    repo = StockGroupRepository(session)
    added = repo.add_if_missing("semis", "NVDA")
    session.commit()
    assert added is True
    assert repo.exists("semis", "NVDA") is True


def test_add_if_missing_skips_existing(seeded_session: Session) -> None:
    repo = StockGroupRepository(seeded_session)
    added = repo.add_if_missing("meme", "GME")
    seeded_session.commit()
    assert added is False
    assert repo.count_total() == 3

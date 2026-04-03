"""Tests for research evaluation DB footprint guard (no silent empty-db success)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.data.database import Base
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.extreme_move_evaluation_service import run_extreme_move_evaluation
from backend.app.services.research_eval_db_guard import (
    ResearchEvalDatabaseEmptyError,
    require_research_eval_db_has_prices,
)


@pytest.mark.unit
def test_require_research_eval_db_has_prices_raises_when_empty() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        with pytest.raises(ResearchEvalDatabaseEmptyError) as ei:
            require_research_eval_db_has_prices(db)
        assert ei.value.stock_count == 0
        assert ei.value.price_row_count == 0
    finally:
        db.close()


@pytest.mark.unit
def test_require_research_eval_db_has_prices_ok_with_one_bar() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Stock(symbol="G", name="G", sector=None, market_cap=None))
        db.add(
            PriceData(
                stock_symbol="G",
                date=date(2024, 1, 2),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
        )
        db.commit()
        require_research_eval_db_has_prices(db)
    finally:
        db.close()


@pytest.mark.unit
def test_run_extreme_move_evaluation_raises_when_db_uninitialized() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        with pytest.raises(ResearchEvalDatabaseEmptyError):
            run_extreme_move_evaluation(db)
    finally:
        db.close()

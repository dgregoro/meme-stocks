"""Unit tests for leader-follower paper trading simulation."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.data.database import Base
from backend.app.data.repositories.leader_follower_paper_trade_repo import LeaderFollowerPaperTradeRepository
from backend.app.models import leader_follower_paper_run  # noqa: F401
from backend.app.models import leader_follower_paper_trade  # noqa: F401
from backend.app.models.leader_follower_signal import LeaderFollowerSignal
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.services.leader_follower_paper_trading_service import (
    PaperTradingConfig,
    apply_round_trip_cost,
    max_drawdown_from_equity,
    run_paper_trading_simulation,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory()


def test_apply_round_trip_cost() -> None:
    assert apply_round_trip_cost(5.0, 0.1) == pytest.approx(4.9)


def test_max_drawdown_from_equity() -> None:
    assert max_drawdown_from_equity([1.0, 1.1, 0.95, 1.0]) > 0


def _add_bar(session: Session, symbol: str, d: date, o: float, c: float) -> None:
    session.add(
        PriceData(
            stock_symbol=symbol,
            date=d,
            open=o,
            high=max(o, c) * 1.01,
            low=min(o, c) * 0.99,
            close=c,
            volume=1_000_000,
        )
    )


@pytest.mark.unit
def test_run_paper_trading_simulation_next_open(session: Session) -> None:
    """One signal with enough bars produces one trade with expected gross/net."""
    session.add(Stock(symbol="GME", name="G", sector=None, market_cap=None))
    session.add(Stock(symbol="AMC", name="A", sector=None, market_cap=None))
    session.commit()

    # next_open on d1 open=100; exit +3 trading days on d4 close=110 => +10% gross
    d0 = date(2026, 1, 6)
    d1 = date(2026, 1, 7)
    d2 = date(2026, 1, 8)
    d3 = date(2026, 1, 9)
    d4 = date(2026, 1, 10)
    for d, o, c in [
        (d0, 100.0, 100.0),
        (d1, 100.0, 101.0),
        (d2, 100.0, 100.0),
        (d3, 100.0, 100.0),
        (d4, 100.0, 110.0),
    ]:
        _add_bar(session, "AMC", d, o, c)
    session.commit()

    session.add(
        LeaderFollowerSignal(
            leader_symbol="GME",
            follower_symbol="AMC",
            group_id="meme",
            signal_date=d0,
            strength_score=0.9,
            leader_return_pct=5.0,
            leader_volume_ratio=2.0,
        )
    )
    session.commit()

    cfg = PaperTradingConfig(
        entry_mode="next_open",
        exit_mode="fixed_days",
        holding_days=3,
        max_positions_per_event=2,
        per_trade_cost_pct=0.1,
    )
    run = run_paper_trading_simulation(session, d0, d4, cfg)
    assert run.total_trades == 1
    assert run.skipped_count == 0
    assert run.cumulative_return_pct == pytest.approx(9.9, rel=1e-5)
    tr = LeaderFollowerPaperTradeRepository(session).list_all_for_run_ordered(run.id)[0]
    assert tr.gross_return_pct == pytest.approx(10.0, rel=1e-5)
    assert tr.net_return_pct == pytest.approx(9.9, rel=1e-5)


@pytest.mark.unit
def test_max_positions_per_event_keeps_stronger_signal(session: Session) -> None:
    from datetime import timedelta

    session.add(Stock(symbol="GME", name="G", sector=None, market_cap=None))
    session.add(Stock(symbol="AMC", name="A", sector=None, market_cap=None))
    session.add(Stock(symbol="BB", name="B", sector=None, market_cap=None))
    session.commit()

    d0 = date(2026, 2, 2)
    days = [d0 + timedelta(days=i) for i in range(8)]
    for d in days:
        for sym in ("AMC", "BB"):
            _add_bar(session, sym, d, 50.0, 50.0)
    session.commit()

    session.add_all(
        [
            LeaderFollowerSignal(
                leader_symbol="GME",
                follower_symbol="AMC",
                group_id="meme",
                signal_date=d0,
                strength_score=0.5,
                leader_return_pct=1.0,
                leader_volume_ratio=1.0,
            ),
            LeaderFollowerSignal(
                leader_symbol="GME",
                follower_symbol="BB",
                group_id="meme",
                signal_date=d0,
                strength_score=0.9,
                leader_return_pct=1.0,
                leader_volume_ratio=1.0,
            ),
        ]
    )
    session.commit()

    cfg = PaperTradingConfig(max_positions_per_event=1, holding_days=3)
    run = run_paper_trading_simulation(session, d0, days[-1], cfg)
    assert run.total_trades == 1
    tr = LeaderFollowerPaperTradeRepository(session).list_all_for_run_ordered(run.id)[0]
    assert tr.follower_symbol == "BB"

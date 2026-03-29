"""Tests for leader_follower_service."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast
from unittest.mock import patch

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Import main to ensure all models are registered (Stock has many relationships)
from backend.app.main import create_app  # noqa: F401
from backend.app.data.database import Base
from backend.app.data.repositories.leader_event_repo import LeaderEventRepository
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.leader_event import LeaderEvent
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock
from backend.app.models.stock_group import StockGroup
from backend.app.services.leader_follower_service import (
    REJECTION_BELOW_RETURN_THRESHOLD,
    REJECTION_INSUFFICIENT_BARS,
    REJECTION_INSUFFICIENT_VOLUME,
    REJECTION_NO_DATA_ON_EVENT_DATE,
    REJECTION_ZERO_AVG_VOLUME,
    compute_event_date,
    create_signals,
    detect_leaders,
    load_symbol_to_primary_group_map,
    run_detection,
    run_detection_for_date,
    select_follower_candidates,
)


def _create_test_session() -> Session:
    """Create in-memory session with all models."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


@pytest.mark.unit
def test_load_symbol_to_primary_group_map_with_symbol_in_multiple_groups_returns_smallest_group_id() -> None:
    """When a symbol is in multiple groups, primary group = lexicographically smallest group_id."""
    session = _create_test_session()

    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))

    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="tech_mega", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="retail", stock_symbol="GME"))
    session.commit()

    result = load_symbol_to_primary_group_map(group_repo)

    assert "GME" in result
    assert result["GME"] == "meme"  # lexicographically smallest of meme, retail, tech_mega


def _seed_price_bars(
    session: Session,
    symbol: str,
    bars: list[tuple[date, float, int]],
) -> None:
    """bars: [(date, close, volume), ...]"""
    price_repo = PriceDataRepository(session)
    for d, close, vol in bars:
        price_repo.add(
            PriceData(
                stock_symbol=symbol,
                date=d,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=vol,
            )
        )


@pytest.mark.unit
def test_leader_detected_when_return_and_volume_exceed_threshold() -> None:
    """Seed price_data with day1 close 100, day2 close 106 (6%), volume 2x avg; assert leader detected."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()

    # 5 bars: avg volume 100, last bar volume 200 (2x), return 6%
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),  # (107-101)/101 = 5.94% return, 2x volume
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 1
    assert events[0].leader_symbol == "GME"
    assert abs(events[0].return_pct - 5.94) < 0.1
    assert abs(events[0].volume_ratio - 2.0) < 0.01
    assert events[0].direction == "up"


@pytest.mark.unit
def test_no_leader_when_return_below_threshold() -> None:
    """Small move; assert no leader."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 100, 100),
            (date(2026, 3, 11), 100, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 100, 100),
            (date(2026, 3, 14), 101, 200),  # 1% return only
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0


@pytest.mark.unit
def test_no_leader_when_volume_below_threshold() -> None:
    """Return qualifies but volume does not; assert no leader."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 106, 110),  # 6% return but volume only 1.1x
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0


@pytest.mark.unit
def test_per_symbol_failure_continues_others() -> None:
    """One symbol has no data; assert others evaluated. errors_count in metrics."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()
    # Only GME has data; AMC has none
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),  # 5.94% return, 2x volume
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    # GME should be detected; AMC skipped (no data)
    assert len(events) == 1
    assert events[0].leader_symbol == "GME"


@pytest.mark.unit
def test_compute_event_date_returns_max_date() -> None:
    """compute_event_date returns max price_data.date across tracked symbols."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    session.commit()
    _seed_price_bars(session, "GME", [(date(2026, 3, 14), 100, 100)])
    session.commit()

    price_repo = PriceDataRepository(session)
    result = compute_event_date(price_repo, stock_repo)
    assert result == date(2026, 3, 14)


@pytest.mark.unit
def test_compute_event_date_returns_none_when_empty() -> None:
    """compute_event_date returns None when no stocks or no price data."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    price_repo = PriceDataRepository(session)
    result = compute_event_date(price_repo, stock_repo)
    assert result is None


@pytest.mark.unit
def test_insufficient_bars_skipped() -> None:
    """Symbol with fewer than 5 bars is skipped."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 13), 100, 100),
            (date(2026, 3, 14), 106, 200),  # only 2 bars
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0


@pytest.mark.unit
def test_multiple_leaders_detected() -> None:
    """Multiple stocks move significantly; one event per qualifying stock."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),  # 5.94% return
        ],
    )
    _seed_price_bars(
        session,
        "AMC",
        [
            (date(2026, 3, 10), 10, 100),
            (date(2026, 3, 11), 10, 100),
            (date(2026, 3, 12), 10, 100),
            (date(2026, 3, 13), 10, 100),
            (date(2026, 3, 14), 10.6, 200),  # (10.6-10)/10 = 6% up, 2x vol
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 2
    symbols = {e.leader_symbol for e in events}
    assert symbols == {"GME", "AMC"}


@pytest.mark.unit
def test_direction_up_vs_down_based_on_return_sign() -> None:
    """Direction is 'up' when return > 0, 'down' when return < 0."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 106, 100),
            (date(2026, 3, 11), 105, 100),
            (date(2026, 3, 12), 104, 100),
            (date(2026, 3, 13), 103, 100),
            (date(2026, 3, 14), 97, 200),  # ~-5.8% down, 2x volume
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 1
    assert events[0].direction == "down"
    assert events[0].return_pct < 0


@pytest.mark.unit
def test_follower_candidate_excluded_when_already_moved() -> None:
    """Leader A, stock_groups {A,B,C}; B has return >= follower_move_threshold; assert B excluded."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    for sym, name in [("A", "Stock A"), ("B", "Stock B"), ("C", "Stock C")]:
        stock_repo.add(Stock(symbol=sym, name=name, sector="X", market_cap=None))
    session.commit()

    group_repo = StockGroupRepository(session)
    for sym in ["A", "B", "C"]:
        group_repo.add(StockGroup(group_id="grp1", stock_symbol=sym))
    session.commit()

    # B moved 5% (>= 3% threshold), C moved 1%
    _seed_price_bars(session, "B", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 105, 100)])
    _seed_price_bars(session, "C", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 101, 100)])
    session.commit()

    leader_event = LeaderEvent(
        leader_symbol="A",
        event_date=date(2026, 3, 14),
        return_pct=6.0,
        volume_ratio=2.0,
        direction="up",
    )
    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.follower_move_threshold_pct = 3.0
        candidates = select_follower_candidates(
            leader_event, group_repo, PriceDataRepository(session), date(2026, 3, 14)
        )

    symbols = [c[0] for c in candidates]
    assert "B" not in symbols
    assert "C" in symbols


@pytest.mark.unit
def test_follower_candidate_included_when_not_moved() -> None:
    """Leader A, stock_groups {A,B,C}; C has small return; assert C is candidate."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    for sym, name in [("A", "Stock A"), ("B", "Stock B"), ("C", "Stock C")]:
        stock_repo.add(Stock(symbol=sym, name=name, sector="X", market_cap=None))
    session.commit()

    group_repo = StockGroupRepository(session)
    for sym in ["A", "B", "C"]:
        group_repo.add(StockGroup(group_id="grp1", stock_symbol=sym))
    session.commit()

    _seed_price_bars(session, "B", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 100.5, 100)])
    _seed_price_bars(session, "C", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 101, 100)])
    session.commit()

    leader_event = LeaderEvent(
        leader_symbol="A",
        event_date=date(2026, 3, 14),
        return_pct=6.0,
        volume_ratio=2.0,
        direction="up",
    )
    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.follower_move_threshold_pct = 3.0
        candidates = select_follower_candidates(
            leader_event, group_repo, PriceDataRepository(session), date(2026, 3, 14)
        )

    symbols = [c[0] for c in candidates]
    assert "B" in symbols
    assert "C" in symbols


@pytest.mark.unit
def test_no_candidates_when_no_group_mapping() -> None:
    """Leader not in stock_groups; assert empty candidates."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="X", name="Stock X", sector="X", market_cap=None))
    session.commit()

    group_repo = StockGroupRepository(session)
    # No group for X
    leader_event = LeaderEvent(
        leader_symbol="X",
        event_date=date(2026, 3, 14),
        return_pct=6.0,
        volume_ratio=2.0,
        direction="up",
    )
    candidates = select_follower_candidates(leader_event, group_repo, PriceDataRepository(session), date(2026, 3, 14))
    assert candidates == []


@pytest.mark.unit
def test_signal_created_with_correct_fields() -> None:
    """Leader + candidates; run signal generation; assert LeaderFollowerSignal has correct fields."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    for sym in ["A", "B", "C"]:
        stock_repo.add(Stock(symbol=sym, name=f"Stock {sym}", sector="X", market_cap=None))
    session.commit()

    group_repo = StockGroupRepository(session)
    for sym in ["A", "B", "C"]:
        group_repo.add(StockGroup(group_id="grp1", stock_symbol=sym))
    session.commit()

    _seed_price_bars(session, "B", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 100.5, 100)])
    _seed_price_bars(session, "C", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 101, 100)])
    session.commit()

    leader_repo = LeaderEventRepository(session)
    signal_repo = LeaderFollowerSignalRepository(session)
    leader_event = LeaderEvent(
        leader_symbol="A",
        event_date=date(2026, 3, 14),
        return_pct=8.0,
        volume_ratio=2.5,
        direction="up",
    )
    leader_repo.add(leader_event)
    session.flush()

    candidates_map = {leader_event.id: [("B", "grp1"), ("C", "grp1")]}
    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_follower_strength_weight_return = 0.6
        mock.return_value.leader_follower_strength_weight_volume = 0.4
        mock.return_value.leader_follower_norm_return_cap_pct = 15.0
        mock.return_value.leader_follower_norm_volume_cap = 4.0
        mock.return_value.leader_follower_cooldown_days = 1
        n = create_signals([leader_event], candidates_map, signal_repo, 1, date(2026, 3, 14))
    session.commit()

    assert n == 2
    signals = signal_repo.list_signals(limit=10)
    assert len(signals) == 2
    for s in signals:
        assert s.leader_symbol == "A"
        assert s.follower_symbol in ("B", "C")
        assert s.group_id == "grp1"
        assert s.strength_score >= 0 and s.strength_score <= 1
        assert s.leader_return_pct == 8.0
        assert s.leader_volume_ratio == 2.5


@pytest.mark.unit
def test_run_detection_short_circuits_when_stock_groups_empty() -> None:
    """When stock_groups is empty, run_detection returns early with grouped_leader_universe_size=0."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    session.commit()

    metrics = run_detection(session)

    assert metrics["grouped_leader_universe_size"] == 0
    assert metrics["input_universe_size"] == 1
    assert metrics["leader_events_detected"] == 0
    assert metrics["follower_candidates_found"] == 0
    assert metrics["signals_emitted"] == 0


@pytest.mark.unit
def test_detect_leaders_ignores_symbols_not_in_groups() -> None:
    """Symbol in stocks with qualifying move but not in stock_groups is not detected as leader."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="UMAC", name="UMAC", sector="X", market_cap=None))
    session.commit()
    # Only GME in stock_groups
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    _seed_price_bars(
        session,
        "UMAC",
        [
            (date(2026, 3, 10), 90, 100),
            (date(2026, 3, 11), 91, 100),
            (date(2026, 3, 12), 92, 100),
            (date(2026, 3, 13), 93, 100),
            (date(2026, 3, 14), 99, 200),  # ~6.5% up, 2x vol
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 1
    assert events[0].leader_symbol == "GME"
    assert "UMAC" not in {e.leader_symbol for e in events}


@pytest.mark.unit
def test_run_detection_includes_grouped_leader_universe_size_in_metrics() -> None:
    """run_detection returns grouped_leader_universe_size in metrics."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    session.commit()

    metrics = run_detection(session)

    assert metrics["grouped_leader_universe_size"] == 1
    assert metrics["input_universe_size"] == 1


@pytest.mark.unit
def test_evaluations_insufficient_bars_has_rejection_reasons() -> None:
    """Symbol with fewer than 5 bars gets evaluation with insufficient_bars."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(session, "GME", [(date(2026, 3, 13), 100, 100), (date(2026, 3, 14), 106, 200)])
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, evaluations = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0
    assert len(evaluations) == 1
    assert evaluations[0]["symbol"] == "GME"
    assert evaluations[0]["rejection_reasons"] == [REJECTION_INSUFFICIENT_BARS]
    assert evaluations[0]["return_pct"] is None
    assert evaluations[0]["volume_ratio"] is None


@pytest.mark.unit
def test_evaluations_no_data_on_event_date() -> None:
    """Symbol with bars but last bar date != event_date gets no_data_on_event_date."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    # 5 bars, but latest is 2026-03-13, not 03-14
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 9), 98, 100),
            (date(2026, 3, 10), 99, 100),
            (date(2026, 3, 11), 100, 100),
            (date(2026, 3, 12), 101, 100),
            (date(2026, 3, 13), 107, 200),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, evaluations = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0
    assert len(evaluations) == 1
    assert evaluations[0]["rejection_reasons"] == [REJECTION_NO_DATA_ON_EVENT_DATE]


@pytest.mark.unit
def test_evaluations_zero_avg_volume() -> None:
    """Symbol with zero avg volume gets zero_avg_volume rejection."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    # Last 4 bars have volume 0; avg of prev 4 = 0
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 0),
            (date(2026, 3, 11), 99, 0),
            (date(2026, 3, 12), 100, 0),
            (date(2026, 3, 13), 101, 0),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, evaluations = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0
    assert len(evaluations) == 1
    assert evaluations[0]["rejection_reasons"] == [REJECTION_ZERO_AVG_VOLUME]


@pytest.mark.unit
def test_evaluations_below_return_threshold_and_insufficient_volume() -> None:
    """Near-miss symbols get both threshold rejection reasons when both fail."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    # 2% return (below 5%), 1.1x volume (below 1.5x)
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 103, 110),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, evaluations = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 0
    assert len(evaluations) == 1
    reasons = cast(list[str], evaluations[0]["rejection_reasons"])
    assert REJECTION_BELOW_RETURN_THRESHOLD in reasons
    assert REJECTION_INSUFFICIENT_VOLUME in reasons
    assert evaluations[0]["return_pct"] is not None
    assert evaluations[0]["volume_ratio"] is not None


@pytest.mark.unit
def test_evaluations_qualified_leader_has_empty_rejection_reasons() -> None:
    """Qualifying leader gets qualified_as_leader=True and empty rejection_reasons."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        events, evaluations = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 1
    assert len(evaluations) == 1
    assert evaluations[0]["qualified_as_leader"] is True
    assert evaluations[0]["rejection_reasons"] == []


@pytest.mark.unit
def test_run_detection_with_run_id_persists_evaluations_and_near_miss_count() -> None:
    """When run_id is set, evaluations are persisted and near_miss_count appears in metrics."""
    from backend.app.data.repositories.leader_debug_repo import LeaderDebugRepository
    from backend.app.models.job_run_history import JobRunHistory

    session = _create_test_session()
    run = JobRunHistory(
        job_name="leader_follower_detection",
        run_at=datetime(2026, 3, 14, 17, 0, 0, tzinfo=timezone.utc),
        success=True,
        error_message=None,
    )
    session.add(run)
    session.flush()
    run_id = run.id

    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    # AMC: near-miss (4% return, 1.3x volume - below 5% and 1.5 thresholds)
    _seed_price_bars(
        session,
        "AMC",
        [
            (date(2026, 3, 10), 10, 100),
            (date(2026, 3, 11), 10, 100),
            (date(2026, 3, 12), 10, 100),
            (date(2026, 3, 13), 10, 100),
            (date(2026, 3, 14), 10.4, 130),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = False
        mock.return_value.leader_follower_cooldown_days = 1
        metrics = run_detection(session, run_id=run_id)
    session.commit()

    assert "near_miss_count" in metrics
    assert metrics["near_miss_count"] == 1
    debug_repo = LeaderDebugRepository(session)
    evals = debug_repo.list_by_run_id(run_id, limit=50)
    assert len(evals) == 2
    symbols = {e.stock_symbol for e in evals}
    assert symbols == {"AMC", "GME"}
    near_misses = debug_repo.list_near_misses_by_run_id(run_id, limit=10)
    assert len(near_misses) == 1
    assert near_misses[0].stock_symbol == "AMC"


@pytest.mark.unit
def test_detect_leaders_uses_debug_thresholds_when_debug_mode_enabled() -> None:
    """With leader_follower_debug_mode=True, relaxed thresholds (3%, 1.2x) are used."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    # ~4% return, 1.3x volume - fails production (5%, 1.5) but passes debug (3%, 1.2)
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 105, 130),  # (105-101)/101 = 3.96%, 130/100 = 1.3x
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = True
        mock.return_value.leader_return_threshold_pct_debug = 3.0
        mock.return_value.leader_volume_spike_threshold_debug = 1.2
        events, _ = detect_leaders(session, date(2026, 3, 14), group_repo.get_all_symbols())

    assert len(events) == 1
    assert events[0].leader_symbol == "GME"


@pytest.mark.unit
def test_run_detection_metrics_include_debug_mode_when_enabled() -> None:
    """run_detection returns debug_mode: true in metrics when leader_follower_debug_mode is True."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    session.commit()

    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_return_threshold_pct = 5.0
        mock.return_value.leader_volume_spike_threshold = 1.5
        mock.return_value.leader_follower_debug_mode = True
        mock.return_value.leader_return_threshold_pct_debug = 3.0
        mock.return_value.leader_volume_spike_threshold_debug = 1.2
        mock.return_value.leader_follower_cooldown_days = 1
        metrics = run_detection(session)

    assert metrics.get("debug_mode") is True


@pytest.mark.unit
def test_deduplication_skips_duplicate_within_cooldown() -> None:
    """Insert signal for (A,B); run again within 1-day cooldown; assert no duplicate."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    for sym in ["A", "B"]:
        stock_repo.add(Stock(symbol=sym, name=f"Stock {sym}", sector="X", market_cap=None))
    session.commit()

    signal_repo = LeaderFollowerSignalRepository(session)
    from backend.app.models.leader_follower_signal import LeaderFollowerSignal

    existing = LeaderFollowerSignal(
        leader_symbol="A",
        follower_symbol="B",
        group_id="grp1",
        signal_date=date(2026, 3, 14),
        strength_score=0.7,
        leader_return_pct=6.0,
        leader_volume_ratio=2.0,
    )
    signal_repo.add(existing)
    session.commit()

    leader_event = LeaderEvent(
        leader_symbol="A",
        event_date=date(2026, 3, 14),
        return_pct=6.0,
        volume_ratio=2.0,
        direction="up",
    )
    leader_repo = LeaderEventRepository(session)
    leader_repo.add(leader_event)
    session.flush()

    candidates_map = {leader_event.id: [("B", "grp1")]}
    with patch("backend.app.services.leader_follower_service.get_settings") as mock:
        mock.return_value.leader_follower_cooldown_days = 1
        n = create_signals([leader_event], candidates_map, signal_repo, 1, date(2026, 3, 14))
    session.commit()

    assert n == 0
    signals = signal_repo.list_signals(limit=10)
    assert len(signals) == 1


@pytest.mark.unit
def test_run_detection_for_date_pair_filtering_reduces_signals_when_enabled() -> None:
    """When enable_pair_filtering_for_signals=True and no pairs pass, 0 signals. When False, 1 signal."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
    group_repo = StockGroupRepository(session)
    group_repo.add(StockGroup(group_id="meme", stock_symbol="GME"))
    group_repo.add(StockGroup(group_id="meme", stock_symbol="AMC"))
    session.commit()
    _seed_price_bars(
        session,
        "GME",
        [
            (date(2026, 3, 10), 98, 100),
            (date(2026, 3, 11), 99, 100),
            (date(2026, 3, 12), 100, 100),
            (date(2026, 3, 13), 101, 100),
            (date(2026, 3, 14), 107, 200),
        ],
    )
    _seed_price_bars(
        session,
        "AMC",
        [
            (date(2026, 3, 10), 10, 100),
            (date(2026, 3, 11), 10, 100),
            (date(2026, 3, 12), 10, 100),
            (date(2026, 3, 13), 10, 100),
            (date(2026, 3, 14), 10.1, 100),
        ],
    )
    session.commit()

    mock_settings = patch("backend.app.services.leader_follower_service.get_settings")
    base_attrs = {
        "leader_return_threshold_pct": 5.0,
        "leader_volume_spike_threshold": 1.5,
        "leader_follower_debug_mode": False,
        "leader_follower_cooldown_days": 1,
        "follower_move_threshold_pct": 3.0,
        "leader_follower_pair_filter_lookback_days": 90,
        "leader_follower_pair_min_signal_count": 2,
        "leader_follower_pair_min_avg_return_1d": 0.0,
        "leader_follower_pair_min_win_rate_1d": 0.5,
        "leader_follower_strength_weight_return": 0.6,
        "leader_follower_strength_weight_volume": 0.4,
        "leader_follower_norm_return_cap_pct": 15.0,
        "leader_follower_norm_volume_cap": 4.0,
    }
    with mock_settings as mock:
        for k, v in base_attrs.items():
            setattr(mock.return_value, k, v)
        mock.return_value.enable_pair_filtering_for_signals = False

        result_off = run_detection_for_date(session, date(2026, 3, 14))
    assert result_off["signals_emitted"] == 1

    with mock_settings as mock:
        for k, v in base_attrs.items():
            setattr(mock.return_value, k, v)
        mock.return_value.enable_pair_filtering_for_signals = True

        result_on = run_detection_for_date(session, date(2026, 3, 14), idempotent=True)
    assert result_on["signals_emitted"] == 0


@pytest.mark.unit
def test_scheduler_job_has_overlap_safeguards() -> None:
    """Verify leader_follower_detection job registered with max_instances=1, coalesce=True, misfire_grace_time=1800."""
    from unittest.mock import MagicMock, patch

    with patch("backend.app.services.scheduler_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            leader_follower_enabled=True,
            leader_follower_job_hour=17,
            price_collection_interval_minutes=15,
            daily_analysis_hour=16,
            notification_check_interval_minutes=30,
            enable_catch_up=False,
            market_timezone="America/New_York",
            market_close_hour_local=16,
            market_close_minute_local=0,
            intraday_ingestion_enabled=False,
        )
        from backend.app.services.scheduler_service import SchedulerService

        scheduler = SchedulerService()
        scheduler.start()
        jobs = scheduler._scheduler.get_jobs()
        lf_jobs = [j for j in jobs if j.id == "leader_follower_detection"]
        assert len(lf_jobs) == 1
        job = lf_jobs[0]
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 1800
        scheduler.shutdown()

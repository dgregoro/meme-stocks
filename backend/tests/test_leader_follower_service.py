"""Tests for leader_follower_service."""

from __future__ import annotations

from datetime import date
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
    compute_event_date,
    create_signals,
    detect_leaders,
    load_symbol_to_primary_group_map,
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
        events = detect_leaders(session, date(2026, 3, 14))

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
        events = detect_leaders(session, date(2026, 3, 14))

    assert len(events) == 0


@pytest.mark.unit
def test_no_leader_when_volume_below_threshold() -> None:
    """Return qualifies but volume does not; assert no leader."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
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
        events = detect_leaders(session, date(2026, 3, 14))

    assert len(events) == 0


@pytest.mark.unit
def test_per_symbol_failure_continues_others() -> None:
    """One symbol has no data; assert others evaluated. errors_count in metrics."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
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
        events = detect_leaders(session, date(2026, 3, 14))

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
        events = detect_leaders(session, date(2026, 3, 14))

    assert len(events) == 0


@pytest.mark.unit
def test_multiple_leaders_detected() -> None:
    """Multiple stocks move significantly; one event per qualifying stock."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))
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
        events = detect_leaders(session, date(2026, 3, 14))

    assert len(events) == 2
    symbols = {e.leader_symbol for e in events}
    assert symbols == {"GME", "AMC"}


@pytest.mark.unit
def test_direction_up_vs_down_based_on_return_sign() -> None:
    """Direction is 'up' when return > 0, 'down' when return < 0."""
    session = _create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
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
        events = detect_leaders(session, date(2026, 3, 14))

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
def test_scheduler_job_has_overlap_safeguards() -> None:
    """Verify leader_follower_detection job registered with max_instances=1, coalesce=True, misfire_grace_time=1800."""
    from unittest.mock import MagicMock, patch

    with patch("backend.app.services.scheduler_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            leader_follower_enabled=True,
            leader_follower_job_hour=17,
            reddit_client_id="",
            reddit_client_secret="",
            reddit_subreddits="wsb",
            reddit_collection_interval_minutes=60,
            price_collection_interval_minutes=15,
            daily_analysis_hour=16,
            notification_check_interval_minutes=30,
            enable_catch_up=False,
            reddit_daily_features_job_hour=17,
            reddit_daily_features_lookback_days=30,
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

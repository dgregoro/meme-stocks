"""Tests for shared research_execution helpers."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.research_execution import (
    ResearchRunEnvelope,
    apply_round_trip_cost,
    compound_equity_from_period_returns,
    max_drawdown_from_equity,
    round_trip_cost_pct_from_bps,
    split_calendar_range,
    split_sorted_trading_days,
)


@pytest.mark.unit
def test_apply_round_trip_cost() -> None:
    assert apply_round_trip_cost(5.0, 0.1) == pytest.approx(4.9)


@pytest.mark.unit
def test_round_trip_bps() -> None:
    assert round_trip_cost_pct_from_bps(10.0) == pytest.approx(0.1)


@pytest.mark.unit
def test_max_drawdown() -> None:
    assert max_drawdown_from_equity([1.0, 1.2, 0.9, 1.1]) > 0


@pytest.mark.unit
def test_max_drawdown_empty() -> None:
    assert max_drawdown_from_equity([]) == 0.0


@pytest.mark.unit
def test_compound_equity() -> None:
    eq = compound_equity_from_period_returns([0.01, -0.02, 0.05])
    assert eq[0] == pytest.approx(1.0)
    assert eq[-1] == pytest.approx(1.01 * 0.98 * 1.05)


@pytest.mark.unit
def test_compound_equity_empty_inputs() -> None:
    assert compound_equity_from_period_returns([]) == [1.0]


@pytest.mark.unit
def test_split_calendar_range_three() -> None:
    start, end = date(2020, 1, 1), date(2020, 1, 10)
    parts = split_calendar_range(start, end, 3)
    assert len(parts) == 3
    assert parts[0][0] == start
    assert parts[-1][1] == end


@pytest.mark.unit
def test_split_calendar_range_single_and_inverted() -> None:
    a, b = date(2020, 1, 1), date(2020, 1, 5)
    assert split_calendar_range(a, b, 1) == [(a, b)]
    with pytest.raises(ValueError, match="start"):
        split_calendar_range(b, a, 3)


@pytest.mark.unit
def test_split_calendar_range_more_chunks_than_days() -> None:
    start, end = date(2020, 1, 1), date(2020, 1, 3)
    assert split_calendar_range(start, end, 10) == [(start, end)]


@pytest.mark.unit
def test_split_sorted_trading_days_empty_and_single_block() -> None:
    assert split_sorted_trading_days([], 3) == []
    one = [date(2020, 1, 1)]
    assert split_sorted_trading_days(one, 5) == [(one[0], one[0])]


@pytest.mark.unit
def test_split_sorted_trading_days() -> None:
    days = [date(2020, 1, i) for i in range(1, 11)]
    parts = split_sorted_trading_days(days, 2)
    assert parts[0] == (days[0], days[4])
    assert parts[1] == (days[5], days[9])


@pytest.mark.unit
def test_research_run_envelope_roundtrip() -> None:
    e = ResearchRunEnvelope.from_context(
        run_kind="s1_merit_report",
        strategy_family="s1",
        eval_start=date(2024, 1, 1),
        eval_end=date(2024, 6, 1),
        universe_label="test100",
        symbols=["SPY", "QQQ", "spy"],
        cost_round_trip_bps=12.0,
        notes="unit test",
    )
    assert e.symbol_count == 2
    d = e.to_json_dict()
    e2 = ResearchRunEnvelope.from_json_dict(d)
    assert e2.symbols_fingerprint_sha256_16 == e.symbols_fingerprint_sha256_16
    assert e2.cost_round_trip_bps == 12.0

"""Tests for research_execution.daily_simple_backtest (spec 020)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from backend.app.services.research_execution.daily_simple_backtest import (
    DailyBar,
    DailySimpleBacktestConfig,
    daily_simple_result_to_jsonable,
    run_daily_simple_long_only_backtest,
)


def _bar(d: date, o: float, h: float, low: float, c: float) -> DailyBar:
    return DailyBar(d=d, open=o, high=h, low=low, close=c)


@pytest.mark.unit
def test_next_open_two_day_horizon_known_gross() -> None:
    """Signal d0 → enter d1 open 100 → exit d2 close 121 → +21% gross."""
    d0, d1, d2 = date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)
    bars = [
        _bar(d0, 100, 100, 100, 100),
        _bar(d1, 100, 110, 99, 100),
        _bar(d2, 110, 125, 100, 121),
    ]
    signals = {d0: 1}
    res = run_daily_simple_long_only_backtest(
        bars,
        signals,
        DailySimpleBacktestConfig(entry="next_open", horizon_days=2, round_trip_cost_bps=0.0),
    )
    assert len(res.trades) == 1
    assert res.trades[0].trade_return_pct_gross == pytest.approx(21.0)
    assert res.skips == []


@pytest.mark.unit
def test_missing_next_bar_skip() -> None:
    d0 = date(2020, 1, 1)
    bars = [_bar(d0, 10, 10, 10, 10)]
    res = run_daily_simple_long_only_backtest(
        bars,
        {d0: 1},
        DailySimpleBacktestConfig(entry="next_open", horizon_days=2),
    )
    assert res.trades == []
    assert len(res.skips) == 1
    assert res.skips[0].reason == "missing_next_bar"
    assert res.skips[0].signal_date == d0


@pytest.mark.unit
def test_net_reduces_by_round_trip_bps() -> None:
    d0, d1, d2 = date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)
    bars = [
        _bar(d0, 100, 100, 100, 100),
        _bar(d1, 100, 100, 100, 100),
        _bar(d2, 100, 121, 100, 121),
    ]
    res = run_daily_simple_long_only_backtest(
        bars,
        {d0: 1},
        DailySimpleBacktestConfig(entry="next_open", horizon_days=2, round_trip_cost_bps=10.0),
    )
    assert len(res.trades) == 1
    assert res.trades[0].trade_return_pct_gross == pytest.approx(21.0)
    assert res.trades[0].trade_return_pct_net == pytest.approx(20.9)


@pytest.mark.unit
def test_jsonable_reporting_is_percent_space() -> None:
    d0, d1, d2 = date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)
    bars = [
        _bar(d0, 100, 100, 100, 100),
        _bar(d1, 100, 100, 100, 100),
        _bar(d2, 100, 121, 100, 121),
    ]
    res = run_daily_simple_long_only_backtest(
        bars,
        {d0: 1},
        DailySimpleBacktestConfig(entry="next_open", horizon_days=2, round_trip_cost_bps=10.0),
    )
    payload = daily_simple_result_to_jsonable(res)
    assert payload["cost_round_trip_bps"] == 10.0
    assert payload["cost_model"] == "fixed_round_trip_bps"
    assert payload["trades"][0]["trade_return_pct_gross"] == pytest.approx(21.0)
    assert payload["trades"][0]["trade_return_pct_net"] == pytest.approx(20.9)
    assert payload["period_trade_return_pct_gross"] == pytest.approx([21.0])
    assert payload["final_cumulative_return_pct_gross"] == pytest.approx(21.0)
    assert payload["cumulative_return_pct_gross"][0] == pytest.approx(0.0)
    assert payload["cumulative_return_pct_gross"][-1] == pytest.approx(21.0)
    assert "gross_simple_return_pct" not in json.dumps(payload)


@pytest.mark.unit
def test_unsorted_bars_rejects() -> None:
    d0, d1 = date(2020, 1, 2), date(2020, 1, 1)
    bars = [_bar(d0, 1, 1, 1, 1), _bar(d1, 1, 1, 1, 1)]
    with pytest.raises(ValueError, match="sorted"):
        run_daily_simple_long_only_backtest(bars, {}, DailySimpleBacktestConfig())

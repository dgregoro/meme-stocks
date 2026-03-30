"""Automated S1 merit report helpers."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.daily_frequency_strategy_research import (
    S2_BUCKET_KEYS,
    _rollup_s1_merit_rolling,
    _rollup_s2_merit_rolling,
    _rollup_s3_merit_rolling,
    _sign_stable,
    _strategy_merit_bundle_summary,
    _top5_concentration,
)
from backend.app.services.s3_vol_term_regime import s3_bucket_keys
from backend.app.services.research_execution.window_splits import (
    split_calendar_range,
    split_sorted_trading_days,
)


@pytest.mark.unit
def test_top5_concentration_uniform() -> None:
    d = {"A": 10, "B": 10, "C": 10, "D": 10, "E": 10, "F": 10}
    assert _top5_concentration(d) == pytest.approx(50 / 60, abs=1e-3)


@pytest.mark.unit
def test_top5_concentration_one_dominant() -> None:
    d = {"A": 100, "B": 1, "C": 1, "D": 1, "E": 1, "F": 1}
    assert _top5_concentration(d) == pytest.approx(104 / 105, rel=1e-3)


@pytest.mark.unit
def test_top5_concentration_empty() -> None:
    assert _top5_concentration({}) == 0.0


@pytest.mark.unit
def test_calendar_splits_three_segments() -> None:
    start, end = date(2020, 1, 1), date(2020, 1, 10)
    parts = split_calendar_range(start, end, 3)
    assert len(parts) == 3
    assert parts[0][0] == start
    assert parts[-1][1] == end


@pytest.mark.unit
def test_sign_stable_same_direction() -> None:
    assert _sign_stable([0.1, 0.2, 0.0]) is True
    assert _sign_stable([-0.1, -0.2]) is True


@pytest.mark.unit
def test_sign_stable_mixed() -> None:
    assert _sign_stable([0.1, -0.2]) is False


@pytest.mark.unit
def test_rollup_rolling_detects_sign_flip() -> None:
    horizons = (1, 5)
    fake = [
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {
                    "hv_lv": {"1": {"avg_excess_vs_baseline_pct": 0.5}},
                },
                "by_regime": {"hv_lv": {"1": {"evaluable_count": 60}}},
            }
        },
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {
                    "hv_lv": {"1": {"avg_excess_vs_baseline_pct": -0.3}},
                },
                "by_regime": {"hv_lv": {"1": {"evaluable_count": 60}}},
            }
        },
    ]
    r = _rollup_s1_merit_rolling(fake, min_events_per_regime=50, horizons=horizons)
    assert r["all_splits_checklist_pass"] is True
    assert r["rolling_pass"] is False
    assert r["excess_vs_baseline_sign_stable"]["hv_lv"]["1"] is False


@pytest.mark.unit
def test_trading_day_chunks_even_split() -> None:
    days = [date(2020, 1, i) for i in range(1, 11)]
    parts = split_sorted_trading_days(days, 2)
    assert len(parts) == 2
    assert parts[0] == (days[0], days[4])
    assert parts[1] == (days[5], days[9])


def test_rollup_s3_detects_sign_flip() -> None:
    horizons = (1,)
    bks = s3_bucket_keys(4)
    q0 = bks[0]
    fake = [
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {q0: {"1": {"avg_excess_vs_baseline_pct": 0.4}}},
                "by_regime": {q0: {"1": {"evaluable_count": 55}}},
            }
        },
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {q0: {"1": {"avg_excess_vs_baseline_pct": -0.2}}},
                "by_regime": {q0: {"1": {"evaluable_count": 55}}},
            }
        },
    ]
    r = _rollup_s3_merit_rolling(fake, min_events_per_bucket=50, horizons=horizons, bucket_keys=bks)
    assert r["rolling_pass"] is False


def test_rollup_s2_detects_sign_flip() -> None:
    horizons = (1,)
    fake = [
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {
                    "gap_up_uptrend": {"1": {"avg_excess_vs_baseline_pct": 0.4}},
                },
                "by_bucket": {"gap_up_uptrend": {"1": {"evaluable_count": 55}}},
            }
        },
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {
                    "gap_up_uptrend": {"1": {"avg_excess_vs_baseline_pct": -0.2}},
                },
                "by_bucket": {"gap_up_uptrend": {"1": {"evaluable_count": 55}}},
            }
        },
    ]
    r = _rollup_s2_merit_rolling(fake, min_events_per_bucket=50, horizons=horizons)
    assert r["rolling_pass"] is False
    assert S2_BUCKET_KEYS[0] == "gap_up_uptrend"


def test_rollup_rolling_passes_when_stable() -> None:
    horizons = (1,)
    fake = [
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {"hv_lv": {"1": {"avg_excess_vs_baseline_pct": 0.1}}},
                "by_regime": {"hv_lv": {"1": {"evaluable_count": 60}}},
            }
        },
        {
            "report": {
                "checklist": {"pass": True},
                "vs_baseline_avg_pct": {"hv_lv": {"1": {"avg_excess_vs_baseline_pct": 0.05}}},
                "by_regime": {"hv_lv": {"1": {"evaluable_count": 60}}},
            }
        },
    ]
    r = _rollup_s1_merit_rolling(fake, min_events_per_regime=50, horizons=horizons)
    assert r["rolling_pass"] is True


@pytest.mark.unit
def test_strategy_merit_bundle_summary_single_and_rolling_pass() -> None:
    single = {"checklist": {"pass": True}}
    rolling = {"rollup": {"rolling_pass": True}}
    s = _strategy_merit_bundle_summary("s1", single, rolling)
    assert s["all_automated_gates_pass"] is True
    assert s["single_window_checklist_pass"] is True
    assert s["rolling_rollup_pass"] is True
    assert s["rolling_included"] is True
    assert s["recommendation"] == "review_against_STRATEGY_CONCLUSION_FRAMEWORK"
    assert s["gate_failures"] == []


@pytest.mark.unit
def test_strategy_merit_bundle_summary_single_only_exploratory() -> None:
    single = {"checklist": {"pass": True}}
    s = _strategy_merit_bundle_summary("s2", single, None)
    assert s["all_automated_gates_pass"] is True
    assert s["rolling_included"] is False
    assert s["rolling_rollup_pass"] is None
    assert "rolling_splits_ge_2" in s["recommendation"]


@pytest.mark.unit
def test_strategy_merit_bundle_summary_rolling_fails_gate() -> None:
    single = {"checklist": {"pass": True}}
    rolling = {"rollup": {"rolling_pass": False}}
    s = _strategy_merit_bundle_summary("s1", single, rolling)
    assert s["all_automated_gates_pass"] is False
    assert "rolling_stability_failed" in s["gate_failures"]


@pytest.mark.unit
def test_strategy_merit_bundle_summary_single_fails_overrides_rolling() -> None:
    single = {"checklist": {"pass": False}}
    rolling = {"rollup": {"rolling_pass": True}}
    s = _strategy_merit_bundle_summary("s1", single, rolling)
    assert s["all_automated_gates_pass"] is False
    assert "single_window_checklist_failed" in s["gate_failures"]

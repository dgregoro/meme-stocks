"""Tests for S7 rule discovery (feature matrix + gated search)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.app.config import get_settings
from backend.app.services.daily_frequency_strategy_research import DailyBar as FreqDailyBar
from backend.app.services.s7_rule_discovery import (
    S7_FEATURE_MATRIX_VERSION,
    build_feature_rows_from_bars,
    enumerate_candidate_rules,
    read_feature_matrix_csv,
    run_rule_search,
    rule_matches_row,
    write_feature_matrix_csv,
    RuleCondition,
    RuleSpec,
    S7FeatureRow,
)


def _bars_uptrend(n: int = 120, *, bump_second_half: float = 0.0) -> list[FreqDailyBar]:
    start = date(2024, 1, 2)
    out: list[FreqDailyBar] = []
    for i in range(n):
        extra = bump_second_half * i if i > n // 2 else 0.0
        c = 100.0 + 0.3 * i + extra
        d = start + timedelta(days=i)
        o = c - 0.15
        out.append(
            FreqDailyBar(
                d=d,
                open=o,
                high=c + 0.25,
                low=c - 0.25,
                close=c,
                volume=500_000 + i * 2_000,
            )
        )
    return out


@pytest.mark.unit
def test_build_feature_rows_non_degenerate() -> None:
    bars = _bars_uptrend(80)
    rows = build_feature_rows_from_bars(bars, vol_z_window=15)
    assert len(rows) >= 40
    assert all(r.ret_1 > -0.5 for r in rows[10:20])  # loose sanity on uptrend


@pytest.mark.unit
def test_rule_matches_row() -> None:
    row = S7FeatureRow(
        d=date(2024, 2, 1),
        ret_1=0.02,
        ret_5=0.05,
        gap_pct=0.001,
        range_pct=0.02,
        vol_z=1.5,
    )
    r = RuleSpec(
        conditions=(
            RuleCondition(feature="ret_1", op="gt", threshold=0.01),
            RuleCondition(feature="vol_z", op="lt", threshold=2.0),
        )
    )
    assert rule_matches_row(row, r) is True
    r2 = RuleSpec(conditions=(RuleCondition(feature="ret_1", op="lt", threshold=0.0),))
    assert rule_matches_row(row, r2) is False


@pytest.mark.unit
def test_run_rule_search_requires_ack() -> None:
    bars = _bars_uptrend(90)
    rows = build_feature_rows_from_bars(bars, vol_z_window=10)
    with pytest.raises(ValueError, match="ack_overfitting"):
        run_rule_search(
            bars=bars,
            feature_rows=rows,
            train_end=rows[40].d,
            ack_overfitting_risk=False,
            symbol="TEST",
        )


@pytest.mark.unit
def test_run_rule_search_top_rules_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S7_MAX_CANDIDATE_RULES", "80")
    monkeypatch.setenv("S7_MAX_RULE_CONDITIONS", "1")
    monkeypatch.setenv("S7_SEARCH_FEATURE_NAMES", "ret_1")
    monkeypatch.setenv("S7_SEARCH_QUANTILES", "0.5")
    monkeypatch.setenv("S7_FORWARD_HORIZON_DAYS", "2")
    get_settings.cache_clear()
    try:
        bars = _bars_uptrend(100, bump_second_half=0.02)
        feat = build_feature_rows_from_bars(bars, vol_z_window=12)
        te = feat[55].d
        out = run_rule_search(
            bars=bars,
            feature_rows=feat,
            train_end=te,
            ack_overfitting_risk=True,
            symbol="ZZZ",
        )
        assert out.get("error") is None
        assert out["kind"] == "s7_rule_discovery_result"
        assert out["feature_matrix_version"] == S7_FEATURE_MATRIX_VERSION
        assert "envelope" in out
        assert isinstance(out["top_rules"], list)
        assert out["top_rules"]
        assert "train_end" in out["protocol"]
        assert out["warnings"]
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_run_rule_search_insufficient_hold_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S7_MIN_HOLD_OUT_FEATURE_ROWS", "20")
    get_settings.cache_clear()
    try:
        bars = _bars_uptrend(60)
        feat = build_feature_rows_from_bars(bars, vol_z_window=10)
        out = run_rule_search(
            bars=bars,
            feature_rows=feat,
            train_end=feat[-3].d,
            ack_overfitting_risk=True,
            symbol="X",
        )
        assert out.get("error") == "insufficient_hold_out"
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_enumerate_respects_max_rules() -> None:
    t0 = date(2024, 1, 2)
    train = [S7FeatureRow(t0 + timedelta(days=i), 0.01 * i, 0.02 * i, 0.001 * i, 0.01, 0.5) for i in range(2, 42)]
    rules = enumerate_candidate_rules(
        train,
        feature_names=["ret_1", "gap_pct"],
        quantile_levels=[0.4, 0.6],
        max_conditions=1,
        max_rules=7,
    )
    assert len(rules) == 7


@pytest.mark.unit
def test_write_read_csv_roundtrip(tmp_path: Path) -> None:
    rows = [
        S7FeatureRow(date(2024, 2, 1), 0.01, 0.02, 0.0, 0.015, 0.3),
        S7FeatureRow(date(2024, 2, 2), -0.005, 0.01, -0.001, 0.02, -0.2),
    ]
    p = tmp_path / "m.csv"
    write_feature_matrix_csv(p, rows, symbol="AB")
    loaded, meta = read_feature_matrix_csv(p)
    assert meta.get("symbol") == "AB"
    assert len(loaded) == 2
    assert loaded[0].ret_1 == pytest.approx(0.01)

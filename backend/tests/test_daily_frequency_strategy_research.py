"""Unit tests for daily-frequency strategy research (S1/S2 building blocks)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.app.services.daily_frequency_strategy_research import (
    DailyBar,
    bars_from_price_rows,
    classify_s1_regime,
    classify_s2_bucket,
    metrics_from_returns,
    realized_vol_series,
    simple_sma,
    volume_log_z_series,
)
from backend.app.services import daily_frequency_strategy_research as dfs_module


@pytest.mark.unit
def test_realized_vol_positive_on_moving_closes() -> None:
    closes = [100.0 + float(i) * 0.5 for i in range(15)]
    rv = realized_vol_series(closes, window=5)
    assert rv[0] is None
    assert rv[4] is None
    assert rv[5] is not None
    assert rv[5] > 0


@pytest.mark.unit
def test_volume_z_spikes_on_last_bar() -> None:
    vols = [1_000_000] * 19 + [10_000_000]
    z = volume_log_z_series(vols, window=20)
    assert z[-1] is not None
    assert z[-1] > 2.0


@pytest.mark.unit
def test_classify_s1_hv_lv() -> None:
    past_rv = [0.01, 0.02, 0.015]
    past_vz = [0.5, 0.4, 0.6]
    r = classify_s1_regime(0.05, -1.0, past_rv, past_vz)
    assert r == "hv_lv"


@pytest.mark.unit
def test_classify_s1_lv_hv() -> None:
    past_rv = [0.03, 0.04, 0.035]
    past_vz = [-0.2, 0.0, 0.1]
    r = classify_s1_regime(0.01, 1.5, past_rv, past_vz)
    assert r == "lv_hv"


@pytest.mark.unit
def test_simple_sma() -> None:
    closes = [float(i) for i in range(1, 30)]
    assert simple_sma(closes, 5, 10) == pytest.approx(sum(closes[6:11]) / 5.0)


@pytest.mark.unit
def test_classify_s2_buckets() -> None:
    assert classify_s2_bucket(1.0, True) == "gap_up_uptrend"
    assert classify_s2_bucket(1.0, False) == "gap_up_downtrend"
    assert classify_s2_bucket(-1.0, False) == "gap_down_downtrend"
    assert classify_s2_bucket(-1.0, True) == "gap_down_uptrend"
    assert classify_s2_bucket(0.0, True) == "flat_gap"


@pytest.mark.unit
def test_bars_from_price_rows_filters_invalid() -> None:
    rows = [
        SimpleNamespace(
            date=date(2024, 1, 2),
            open=10.0,
            high=11.0,
            low=9.0,
            close=0.0,
            volume=100,
        ),
        SimpleNamespace(
            date=date(2024, 1, 3),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.0,
            volume=100,
        ),
    ]
    bars = bars_from_price_rows(rows)  # type: ignore[arg-type]
    assert len(bars) == 1
    assert bars[0].d == date(2024, 1, 3)


@pytest.mark.unit
def test_parse_horizons_defaults_and_invalid() -> None:
    assert dfs_module._parse_horizons_setting(None) == (1, 5, 10)
    assert dfs_module._parse_horizons_setting("") == (1, 5, 10)
    assert dfs_module._parse_horizons_setting("  ,  ") == (1, 5, 10)
    assert dfs_module._parse_horizons_setting("10, 3, 3") == (3, 10)
    assert dfs_module._parse_horizons_setting("notints") == (1, 5, 10)


@pytest.mark.unit
def test_metrics_from_returns_empty_and_median_branches() -> None:
    z = metrics_from_returns([])
    assert z["evaluable_count"] == 0
    assert z["win_rate"] == 0.0
    one = metrics_from_returns([0.02])
    assert one["evaluable_count"] == 1
    assert one["median_return_pct"] == 0.02
    even = metrics_from_returns([-0.01, 0.03])
    assert even["median_return_pct"] == pytest.approx(0.01, abs=1e-4)
    mix = metrics_from_returns([0.1, -0.05, 0.02])
    assert mix["win_rate"] == pytest.approx(2 / 3, abs=1e-4)


@pytest.mark.unit
def test_macro_vol_term_data_hint_non_empty() -> None:
    h = dfs_module._macro_vol_term_data_hint()
    assert "VIX" in h
    assert "backfill vol-term" in h


@pytest.mark.unit
def test_price_close_dict_empty_and_series() -> None:
    assert dfs_module._price_close_dict([]) == {}
    bars = [
        DailyBar(date(2024, 1, 2), 1, 1, 1, 10.0, 100),
        DailyBar(date(2024, 1, 3), 1, 1, 1, 11.0, 100),
    ]
    d = dfs_module._price_close_dict(bars)
    assert "_series" in d
    assert d["_series"] == [(date(2024, 1, 2), 10.0), (date(2024, 1, 3), 11.0)]


@pytest.mark.unit
def test_classify_s1_insufficient_prior_and_neutral_tie() -> None:
    assert classify_s1_regime(0.1, 0.1, [0.01], [0.02]) is None
    past_rv = [0.02, 0.02, 0.02]
    past_vz = [0.0, 0.0, 0.0]
    assert classify_s1_regime(0.02, 0.0, past_rv, past_vz) == "neutral"


@pytest.mark.unit
def test_classify_s2_uptrend_none() -> None:
    assert classify_s2_bucket(1.0, None) is None


@pytest.mark.unit
def test_realized_vol_bad_window() -> None:
    with pytest.raises(ValueError, match="window"):
        realized_vol_series([100.0, 101.0], window=1)


@pytest.mark.unit
def test_volume_z_bad_window_and_zero_variance_skips() -> None:
    with pytest.raises(ValueError, match="window"):
        volume_log_z_series([100, 100], window=1)
    flat = [1_000_000] * 25
    z = volume_log_z_series(flat, window=10)
    assert all(v is None for v in z)


@pytest.mark.unit
def test_simple_sma_invalid_ranges() -> None:
    closes = [10.0, 11.0]
    assert simple_sma(closes, 5, 1) is None
    assert simple_sma(closes, 2, 0) is None
    assert simple_sma([10.0, -1.0], 2, 1) is None

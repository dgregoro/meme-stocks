"""Unit tests for daily-frequency strategy research (S1/S2 building blocks)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.app.services.daily_frequency_strategy_research import (
    bars_from_price_rows,
    classify_s1_regime,
    classify_s2_bucket,
    realized_vol_series,
    simple_sma,
    volume_log_z_series,
)


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

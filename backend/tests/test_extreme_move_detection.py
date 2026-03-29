"""Unit tests for extreme move classification helpers (016)."""

from __future__ import annotations

import pytest

from backend.app.services.extreme_move_detection import (
    classify_extreme_move,
    compute_daily_return_pct,
    get_magnitude_bucket,
    get_volume_bucket,
)


@pytest.mark.unit
def test_compute_daily_return_pct() -> None:
    assert compute_daily_return_pct(110.0, 100.0) == 10.0
    assert compute_daily_return_pct(90.0, 100.0) == -10.0
    assert compute_daily_return_pct(100.0, 100.0) == 0.0
    assert compute_daily_return_pct(100.0, 0.0) is None


@pytest.mark.unit
def test_classify_extreme_move_thresholds() -> None:
    assert classify_extreme_move(6.0, 5.0, 5.0) == "extreme_up"
    assert classify_extreme_move(-6.0, 5.0, 5.0) == "extreme_down"
    assert classify_extreme_move(4.9, 5.0, 5.0) is None
    assert classify_extreme_move(-4.9, 5.0, 5.0) is None


@pytest.mark.unit
def test_classify_both_sides_tie_break() -> None:
    """If both up and down thresholds hit (e.g. zero return with 0% thresholds), research tie-break."""
    assert classify_extreme_move(0.01, 0.0, 0.0) == "extreme_up"
    assert classify_extreme_move(-0.01, 0.0, 0.0) == "extreme_down"
    assert classify_extreme_move(0.0, 0.0, 0.0) == "extreme_up"


@pytest.mark.unit
def test_classify_negative_threshold_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        classify_extreme_move(1.0, -1.0, 5.0)


@pytest.mark.unit
def test_get_magnitude_bucket_edges() -> None:
    assert get_magnitude_bucket(9.0) == "8+"
    assert get_magnitude_bucket(-9.0) == "8+"
    assert get_magnitude_bucket(6.0) == "5-8"
    assert get_magnitude_bucket(4.0) == "3-5"
    assert get_magnitude_bucket(2.0) == "other"


@pytest.mark.unit
def test_get_volume_bucket_edges() -> None:
    hi, ex = 1.5, 3.0
    assert get_volume_bucket(None, hi, ex) == "unknown"
    assert get_volume_bucket(1.0, hi, ex) == "normal"
    assert get_volume_bucket(2.0, hi, ex) == "high"
    assert get_volume_bucket(4.0, hi, ex) == "extreme"
    assert get_volume_bucket(2.0, 0.0, 3.0) == "unknown"

"""Unit tests for volume spike pure detection helpers."""

from __future__ import annotations

import pytest

from backend.app.services.volume_spike_detection import (
    classify_event_type,
    compute_baseline_volume,
    compute_same_day_return_pct,
    is_volume_spike,
)


@pytest.mark.unit
def test_baseline_median_and_mean() -> None:
    assert compute_baseline_volume([100, 200, 300], "median") == 200.0
    assert compute_baseline_volume([100, 200, 300], "mean") == 200.0
    assert compute_baseline_volume([], "median") is None
    assert compute_baseline_volume([0, 0], "mean") is None


@pytest.mark.unit
def test_same_day_return_pct() -> None:
    assert compute_same_day_return_pct(101.0, 100.0) == 1.0
    assert compute_same_day_return_pct(99.0, 100.0) == -1.0
    assert compute_same_day_return_pct(100.0, 0.0) is None


@pytest.mark.unit
def test_classify_event_type_bands() -> None:
    assert classify_event_type(1.0, 0.5) == "spike_up"
    assert classify_event_type(-1.0, 0.5) == "spike_down"
    assert classify_event_type(0.2, 0.5) == "spike_flat"


@pytest.mark.unit
def test_is_volume_spike_ratio() -> None:
    assert is_volume_spike(3000, 1000.0, 3.0) is True
    assert is_volume_spike(2999, 1000.0, 3.0) is False
    assert is_volume_spike(100, 0.0, 3.0) is False

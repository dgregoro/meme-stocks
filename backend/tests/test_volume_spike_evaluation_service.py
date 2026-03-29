"""Unit tests for volume spike evaluation aggregates."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.models.volume_spike_event import VolumeSpikeEvent
from backend.app.services.volume_spike_evaluation_service import aggregate_volume_spike_summary


@pytest.mark.unit
def test_aggregate_summary_forward_return_from_event_close() -> None:
    """Known closes: ref day 100, +1 trading day 110 -> +10%."""
    d0 = date(2024, 1, 2)
    d1 = date(2024, 1, 3)
    d2 = date(2024, 1, 4)
    ev = VolumeSpikeEvent(
        symbol="T",
        event_date=d1,
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_up",
    )
    price_by_symbol = {
        "T": [
            (d0, 100.0),
            (d1, 100.0),
            (d2, 110.0),
        ]
    }
    summary = aggregate_volume_spike_summary([ev], price_by_symbol, horizons=(1,))
    h1 = summary["by_horizon"]["1d"]
    assert h1["evaluable_count"] == 1
    assert h1["avg_return_pct"] == 10.0
    assert h1["win_rate"] == 1.0
    up = summary["by_event_type"]["spike_up"]["1d"]
    assert up["evaluable_count"] == 1


@pytest.mark.unit
def test_aggregate_summary_missing_forward_data() -> None:
    ev = VolumeSpikeEvent(
        symbol="T",
        event_date=date(2024, 1, 2),
        volume=1,
        baseline_volume=1.0,
        volume_ratio=1.0,
        same_day_return_pct=0.0,
        event_type="spike_flat",
    )
    price_by_symbol = {"T": [(date(2024, 1, 2), 100.0)]}
    summary = aggregate_volume_spike_summary([ev], price_by_symbol, horizons=(1, 3))
    assert summary["by_horizon"]["1d"]["evaluable_count"] == 0
    assert summary["by_horizon"]["3d"]["evaluable_count"] == 0


@pytest.mark.unit
def test_empty_events_summary() -> None:
    s = aggregate_volume_spike_summary([], {}, horizons=(1, 3))
    assert s["total_events"] == 0
    assert s["date_range"]["since"] is None

"""Pure functions: rolling baseline volume, same-day return, spike classification (015)."""

from __future__ import annotations

from statistics import mean, median
from typing import Literal, Sequence

EventType = Literal["spike_up", "spike_down", "spike_flat"]


def compute_baseline_volume(prior_volumes: Sequence[int], statistic: str) -> float | None:
    """Baseline over W prior trading days. statistic: 'mean' or 'median' (default median if unknown)."""
    if not prior_volumes:
        return None
    stat = statistic.strip().lower()
    if stat == "mean":
        val = float(mean(prior_volumes))
    else:
        val = float(median(prior_volumes))
    if val <= 0:
        return None
    return val


def compute_same_day_return_pct(close_event: float, close_prev: float) -> float | None:
    """Close-to-close return on event day in percent. None if prior close invalid."""
    if close_prev <= 0:
        return None
    return round((close_event / close_prev - 1.0) * 100.0, 4)


def classify_event_type(return_pct: float, flat_band_pct: float) -> EventType:
    """spike_up / spike_down / spike_flat from same-day return vs symmetric band."""
    if return_pct >= flat_band_pct:
        return "spike_up"
    if return_pct <= -flat_band_pct:
        return "spike_down"
    return "spike_flat"


def is_volume_spike(day_volume: int, baseline_volume: float, ratio_threshold: float) -> bool:
    if baseline_volume <= 0 or ratio_threshold <= 0:
        return False
    return (day_volume / baseline_volume) >= ratio_threshold

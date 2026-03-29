"""Pure helpers: daily return and extreme-move classification (016)."""

from __future__ import annotations

from typing import Literal

EventType = Literal["extreme_up", "extreme_down"]


def compute_daily_return_pct(close_event: float, close_prev: float) -> float | None:
    """Close-to-close return on event day in percent. None if prior close invalid."""
    if close_prev <= 0:
        return None
    return round((close_event / close_prev - 1.0) * 100.0, 4)


def classify_extreme_move(
    return_pct: float,
    up_threshold_pct: float,
    down_threshold_pct: float,
) -> EventType | None:
    """Return extreme_up / extreme_down / None. Thresholds are positive magnitudes for each side."""
    if up_threshold_pct < 0 or down_threshold_pct < 0:
        raise ValueError("thresholds must be non-negative")
    up_hit = return_pct >= up_threshold_pct
    down_hit = return_pct <= -down_threshold_pct
    if up_hit and down_hit:
        if return_pct > 0:
            return "extreme_up"
        if return_pct < 0:
            return "extreme_down"
        return "extreme_up"
    if up_hit:
        return "extreme_up"
    if down_hit:
        return "extreme_down"
    return None


def get_magnitude_bucket(pct_move: float) -> str:
    """Bucket by absolute close-to-close move (percent), for context filters (017)."""
    abs_move = abs(pct_move)
    if abs_move >= 8:
        return "8+"
    if abs_move >= 5:
        return "5-8"
    if abs_move >= 3:
        return "3-5"
    return "other"


def get_volume_bucket(ratio: float | None, high_ratio: float, extreme_ratio: float) -> str:
    """Classify volume vs rolling baseline: normal / high / extreme / unknown (017)."""
    if ratio is None:
        return "unknown"
    if extreme_ratio <= 0 or high_ratio <= 0:
        return "unknown"
    if ratio >= extreme_ratio:
        return "extreme"
    if ratio >= high_ratio:
        return "high"
    return "normal"

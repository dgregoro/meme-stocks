from __future__ import annotations

from dataclasses import dataclass

from backend.app.config import get_settings
from backend.app.services.sentiment_analyzer import SentimentSummary


@dataclass(frozen=True)
class ActivitySignal:
    """Represents a single unusual activity signal."""

    kind: str  # 'volume_spike' | 'price_movement' | 'sentiment_shift'
    severity: str  # 'low' | 'medium' | 'high'
    message: str


def detect_volume_spike(current_volume: int, average_volume: int) -> ActivitySignal | None:
    """Return an ActivitySignal if current volume exceeds configured threshold vs average.

    Uses volume_spike_threshold from config. Returns None if average is 0 or ratio is below threshold.
    """
    if average_volume <= 0:
        return None

    settings = get_settings()
    ratio = current_volume / float(average_volume)
    if ratio <= settings.volume_spike_threshold:
        return None

    severity = "high" if ratio >= settings.volume_spike_threshold * 1.5 else "medium"
    return ActivitySignal(
        kind="volume_spike",
        severity=severity,
        message=f"Volume {ratio:.1f}x average",
    )


def detect_price_movement(current_price: float, reference_price: float) -> ActivitySignal | None:
    if reference_price <= 0:
        return None

    settings = get_settings()
    change_pct = (current_price - reference_price) / reference_price * 100.0
    threshold = settings.price_movement_threshold_pct

    if abs(change_pct) <= threshold:
        return None

    severity = "high" if abs(change_pct) >= threshold * 2 else "medium"
    direction = "up" if change_pct > 0 else "down"
    return ActivitySignal(
        kind="price_movement",
        severity=severity,
        message=f"Price moved {change_pct:.2f}% ({direction})",
    )


def detect_sentiment_shift(current: SentimentSummary, previous: SentimentSummary | None) -> ActivitySignal | None:
    """Return an ActivitySignal if sentiment score changed beyond configured threshold.

    Compares current vs previous summary. Returns None if either score is missing or delta is below threshold.
    """
    if current.score is None or previous is None or previous.score is None:
        return None

    settings = get_settings()
    delta = current.score - previous.score
    if abs(delta) <= settings.sentiment_shift_threshold:
        return None

    severity = "high" if abs(delta) >= settings.sentiment_shift_threshold * 2 else "medium"
    direction = "positive" if delta > 0 else "negative"
    return ActivitySignal(
        kind="sentiment_shift",
        severity=severity,
        message=f"Sentiment shifted {direction} by {delta:.2f}",
    )

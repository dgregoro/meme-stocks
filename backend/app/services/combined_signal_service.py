"""Combined signal aggregation for multi-signal alerts.

Aggregates volume, price, sentiment, and RSI signals into a weighted score.
Combined alerts are created only when score >= threshold and at least 2 signals fired.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.config import get_settings
from backend.app.services.activity_detector import ActivitySignal
from backend.app.services.pattern_analyzer import PriceTrend


@dataclass(frozen=True)
class SignalEvaluated:
    """A single signal evaluated for a ticker."""

    signal_type: str  # 'sentiment_shift' | 'price_movement' | 'volume_spike' | 'rsi_signal'
    raw_value: str | float | None
    fired: bool
    contribution: float
    reason: str | None = None


@dataclass(frozen=True)
class CombinedEvaluation:
    """Result of aggregating signals for a ticker."""

    symbol: str
    signals_evaluated: tuple[SignalEvaluated, ...]
    combined_score: float
    threshold: float
    threshold_met: bool
    evaluation_timestamp: datetime


def from_activity_signal(
    signal: ActivitySignal | None, signal_type: str, weight: float
) -> SignalEvaluated:
    """Convert ActivitySignal to SignalEvaluated. None yields fired=False, contribution=0."""
    if signal is None:
        return SignalEvaluated(
            signal_type=signal_type,
            raw_value=None,
            fired=False,
            contribution=0.0,
            reason="No signal",
        )
    return SignalEvaluated(
        signal_type=signal.kind,
        raw_value=signal.message,
        fired=True,
        contribution=weight,
        reason=None,
    )


def from_rsi_signal(rsi_signal: str | None, rsi_value: float | None, weight: float) -> SignalEvaluated:
    """Convert PriceTrend.rsi_signal to SignalEvaluated. neutral/None yields fired=False."""
    if rsi_signal is None or rsi_signal == "neutral":
        return SignalEvaluated(
            signal_type="rsi_signal",
            raw_value=rsi_value,
            fired=False,
            contribution=0.0,
            reason="RSI neutral or unavailable",
        )
    return SignalEvaluated(
        signal_type="rsi_signal",
        raw_value=rsi_value,
        fired=True,
        contribution=weight,
        reason=None,
    )


def evaluate(symbol: str, signals: list[SignalEvaluated]) -> CombinedEvaluation:
    """Aggregate signals into a combined score. threshold_met when score >= threshold and >= 2 fired."""
    settings = get_settings()
    threshold = settings.combined_signal_threshold
    combined_score = sum(s.contribution for s in signals)
    fired_count = sum(1 for s in signals if s.fired)
    # Per SC-001: single-signal-only cases produce no combined alert
    threshold_met = combined_score >= threshold and fired_count >= 2
    return CombinedEvaluation(
        symbol=symbol,
        signals_evaluated=tuple(signals),
        combined_score=combined_score,
        threshold=threshold,
        threshold_met=threshold_met,
        evaluation_timestamp=datetime.now(timezone.utc),
    )


def serialize_signal_metadata(ev: CombinedEvaluation) -> str:
    """Serialize CombinedEvaluation to JSON string for storage."""
    payload: dict[str, Any] = {
        "evaluation_timestamp": ev.evaluation_timestamp.isoformat(),
        "combined_score": ev.combined_score,
        "threshold": ev.threshold,
        "signals_evaluated": [
            {
                "signal_type": s.signal_type,
                "raw_value": s.raw_value,
                "fired": s.fired,
                "contribution": s.contribution,
                "reason": s.reason,
            }
            for s in ev.signals_evaluated
        ],
    }
    return json.dumps(payload)


def parse_signal_metadata(s: str | None) -> dict[str, Any] | None:
    """Parse signal_metadata JSON string. Returns None for empty/invalid input."""
    if s is None or not s.strip():
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None

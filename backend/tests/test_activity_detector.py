from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.services.activity_detector import (
    ActivitySignal,
    detect_price_movement,
    detect_sentiment_shift,
    detect_volume_spike,
)
from backend.app.services.sentiment_analyzer import SentimentSummary


def test_detect_volume_spike_uses_thresholds() -> None:
    # Below threshold -> no signal
    assert detect_volume_spike(current_volume=1000, average_volume=900) is None

    # Above threshold -> signal
    sig = detect_volume_spike(current_volume=3000, average_volume=1000)
    assert isinstance(sig, ActivitySignal)
    assert sig.kind == "volume_spike"
    assert sig.severity in {"medium", "high"}


def test_detect_price_movement_thresholds() -> None:
    # Small move -> no signal
    assert detect_price_movement(current_price=105, reference_price=100) is None

    # Big move -> signal
    sig = detect_price_movement(current_price=120, reference_price=100)
    assert isinstance(sig, ActivitySignal)
    assert sig.kind == "price_movement"
    assert sig.severity in {"medium", "high"}


def test_detect_sentiment_shift_requires_previous_and_scores() -> None:
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    current = SentimentSummary(
        stock_symbol="GME",
        score=0.8,
        mention_count=10,
        window=timedelta(hours=24),
        calculated_at=now,
    )
    previous_no_score = SentimentSummary(
        stock_symbol="GME",
        score=None,
        mention_count=0,
        window=timedelta(hours=24),
        calculated_at=now - timedelta(hours=24),
    )

    assert detect_sentiment_shift(current, None) is None
    assert detect_sentiment_shift(current, previous_no_score) is None

    previous = SentimentSummary(
        stock_symbol="GME",
        score=0.0,
        mention_count=5,
        window=timedelta(hours=24),
        calculated_at=now - timedelta(hours=24),
    )

    sig = detect_sentiment_shift(current, previous)
    assert isinstance(sig, ActivitySignal)
    assert sig.kind == "sentiment_shift"
    assert sig.severity in {"medium", "high"}



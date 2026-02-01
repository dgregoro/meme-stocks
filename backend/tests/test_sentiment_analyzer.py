from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    analyze_post_sentiment,
    calculate_weighted_sentiment,
    classify_sentiment,
)


@dataclass
class DummyPost:
    title: str
    upvotes: int
    comments: int
    collected_at: datetime


def test_analyze_post_sentiment_basic_keywords() -> None:
    assert analyze_post_sentiment("This is so bullish, buy and hold") > 0
    assert analyze_post_sentiment("This will crash, total scam, sell") < 0
    assert analyze_post_sentiment("No strong opinion here") == 0.0


def test_calculate_weighted_sentiment_no_posts_returns_no_data() -> None:
    now = datetime(2024, 1, 2, tzinfo=timezone.utc)
    summary = calculate_weighted_sentiment("GME", posts=[], window=timedelta(hours=24), now=now)
    assert isinstance(summary, SentimentSummary)
    assert summary.score is None
    assert summary.mention_count == 0


def test_calculate_weighted_sentiment_with_engagement_and_decay() -> None:
    now = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    recent = DummyPost(
        title="GME to the moon buy buy",
        upvotes=100,
        comments=20,
        collected_at=now - timedelta(hours=1),
    )
    old = DummyPost(
        title="GME is a scam sell",
        upvotes=10,
        comments=2,
        collected_at=now - timedelta(hours=20),
    )

    summary = calculate_weighted_sentiment("GME", posts=[recent, old], window=timedelta(hours=24), now=now)

    assert summary.mention_count == 2
    # Recent, highly upvoted positive post should dominate.
    assert summary.score is not None
    assert summary.score > 0


def test_classify_sentiment_uses_thresholds() -> None:
    assert classify_sentiment(None) == "no_data"
    # Using defaults from config: positive >= 0.3, negative <= -0.2
    assert classify_sentiment(0.5) == "positive"
    assert classify_sentiment(-0.5) == "negative"
    assert classify_sentiment(0.0) == "neutral"

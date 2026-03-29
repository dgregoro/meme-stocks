from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp, log10
from typing import Iterable, Protocol

from backend.app.config import get_settings


class HasPostTextFields(Protocol):
    """Minimal shape for keyword sentiment scoring (title + engagement)."""

    title: str
    upvotes: int
    comments: int
    collected_at: datetime


def _parse_keywords(csv: str) -> frozenset[str]:
    """Parse comma-separated keyword string into a frozenset of lowercase tokens."""
    return frozenset(kw.strip().lower() for kw in csv.split(",") if kw.strip())


def _get_sentiment_keywords() -> tuple[frozenset[str], frozenset[str]]:
    """Load positive and negative keyword sets from config."""
    settings = get_settings()
    pos = _parse_keywords(settings.sentiment_positive_keywords)
    neg = _parse_keywords(settings.sentiment_negative_keywords)
    # Fallback to defaults if config yields empty sets
    default_pos = frozenset({"buy", "moon", "hold", "bullish", "gains", "profit", "long"})
    default_neg = frozenset({"sell", "crash", "bearish", "loss", "dump", "scam", "short"})
    return (pos or default_pos, neg or default_neg)


def analyze_post_sentiment(text: str) -> float:
    """Very simple keyword-based sentiment score in [-1, 1].

    Uses positive/negative keyword sets from config (sentiment_positive_keywords,
    sentiment_negative_keywords). Intentionally naive and deterministic; can be
    replaced with a more advanced model later without changing callers.
    """
    pos_keywords, neg_keywords = _get_sentiment_keywords()
    lower = text.lower()
    pos_matches = sum(1 for kw in pos_keywords if kw in lower)
    neg_matches = sum(1 for kw in neg_keywords if kw in lower)

    if pos_matches == 0 and neg_matches == 0:
        return 0.0

    score = (pos_matches - neg_matches) / float(pos_matches + neg_matches)
    # Clamp to [-1, 1] just in case
    return max(-1.0, min(1.0, score))


@dataclass(frozen=True)
class SentimentSummary:
    stock_symbol: str
    score: float | None  # None indicates "no data"
    mention_count: int
    window: timedelta
    calculated_at: datetime


def calculate_weighted_sentiment(
    stock_symbol: str,
    posts: Iterable[HasPostTextFields],
    *,
    window: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> SentimentSummary:
    """Aggregate sentiment over a time window with engagement and time weighting.

    Returns SentimentSummary with score=None if there are no posts in the window.
    """

    if now is None:
        # Use a timezone-aware UTC timestamp; if stored datetimes are naive,
        # comparisons may fail and should be normalized at the persistence layer.
        now = datetime.now(timezone.utc)

    relevant_posts: list[HasPostTextFields] = []
    cutoff = now - window
    for post in posts:
        collected_at = post.collected_at
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        if collected_at >= cutoff:
            relevant_posts.append(post)

    if not relevant_posts:
        return SentimentSummary(
            stock_symbol=stock_symbol,
            score=None,
            mention_count=0,
            window=window,
            calculated_at=now,
        )

    total_weighted_sentiment = 0.0
    total_weight = 0.0

    for post in relevant_posts:
        post_sentiment = analyze_post_sentiment(post.title or "")
        engagement_weight = log10(post.upvotes + post.comments + 1)
        collected_at = post.collected_at
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        hours_old = max(0.0, (now - collected_at).total_seconds() / 3600.0)
        time_weight = exp(-hours_old / 24.0)
        weight = engagement_weight * time_weight

        total_weighted_sentiment += post_sentiment * weight
        total_weight += weight

    if total_weight == 0.0:
        score: float | None = 0.0
    else:
        score = total_weighted_sentiment / total_weight

    return SentimentSummary(
        stock_symbol=stock_symbol,
        score=score,
        mention_count=len(relevant_posts),
        window=window,
        calculated_at=now,
    )


def classify_sentiment(score: float | None) -> str:
    """Classify aggregated sentiment using thresholds from configuration.

    Returns one of: 'positive', 'negative', 'neutral', or 'no_data'.
    """

    if score is None:
        return "no_data"

    settings = get_settings()
    if score >= settings.sentiment_positive_threshold:
        return "positive"
    if score <= settings.sentiment_negative_threshold:
        return "negative"
    return "neutral"

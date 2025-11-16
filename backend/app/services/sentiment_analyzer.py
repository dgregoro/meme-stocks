from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp, log10
from typing import Iterable, Protocol

from backend.app.config import get_settings


class HasRedditFields(Protocol):
    """Protocol for objects that can be analyzed for sentiment.

    This matches both DB models (RedditPost) and normalized dataclasses
    (RedditPostData) without creating a hard dependency.
    """

    title: str
    upvotes: int
    comments: int
    collected_at: datetime


POSITIVE_KEYWORDS = {"buy", "moon", "hold", "bullish", "gains", "profit", "long"}
NEGATIVE_KEYWORDS = {"sell", "crash", "bearish", "loss", "dump", "scam", "short"}


def analyze_post_sentiment(text: str) -> float:
    """Very simple keyword-based sentiment score in [-1, 1].

    This is intentionally naive and deterministic; it can be replaced with
    a more advanced model later without changing callers.
    """

    lower = text.lower()
    pos_matches = sum(1 for kw in POSITIVE_KEYWORDS if kw in lower)
    neg_matches = sum(1 for kw in NEGATIVE_KEYWORDS if kw in lower)

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
    posts: Iterable[HasRedditFields],
    *,
    window: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> SentimentSummary:
    """Aggregate sentiment over a time window with engagement and time weighting.

    Returns SentimentSummary with score=None if there are no posts in the window.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    relevant_posts: list[HasRedditFields] = []
    cutoff = now - window
    for post in posts:
        if post.collected_at >= cutoff:
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
        post_sentiment = analyze_post_sentiment(post.title)
        engagement_weight = log10(post.upvotes + post.comments + 1)
        hours_old = max(0.0, (now - post.collected_at).total_seconds() / 3600.0)
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



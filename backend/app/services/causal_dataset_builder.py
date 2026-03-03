"""Time series dataset builder for lead-lag causal analysis.

Builds aligned series: mention counts, aggregated sentiment, price close, and returns
per time bucket. No look-ahead: bucket sentiment/mentions only from posts whose
collected_at falls inside that bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp, log10
from typing import Literal

import numpy as np
import pandas as pd

from backend.app.config import get_settings
from backend.app.feature_store.parquet_reader import read_bars
from backend.app.services.sentiment_analyzer import analyze_post_sentiment

Freq = Literal["15min", "1h", "1d"]

# Pandas frequency strings for resampling
FREQ_MAP: dict[str, str] = {
    "15min": "15min",
    "1h": "1h",
    "1d": "1D",
}


@dataclass(frozen=True)
class InsufficientDataResult:
    """Returned when there is not enough data for analysis."""

    symbol: str
    freq: str
    reason: str
    buckets_available: int
    min_required: int


@dataclass(frozen=True)
class CausalDataset:
    """Aligned time series dataset for causal analysis.

    DataFrame is indexed by bucket timestamp (UTC). Columns:
    - mentions: count of Reddit posts in bucket
    - sentiment_mean: mean sentiment (optionally weighted) in bucket
    - price_close: last close in bucket
    - returns: log(price_close).diff()
    """

    df: pd.DataFrame
    symbol: str
    freq: str
    start_utc: datetime
    end_utc: datetime
    sample_size: int


def _min_buckets(freq: str) -> int:
    """Return minimum required buckets for the given frequency."""
    settings = get_settings()
    if freq == "15min":
        return settings.causal_min_buckets_15m
    if freq == "1h":
        return settings.causal_min_buckets_1h
    if freq == "1d":
        return settings.causal_min_buckets_1d
    return settings.causal_min_buckets_1h


def _resample_bars(bars: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Resample minute bars to target frequency. Close=last, volume=sum."""
    if bars.empty:
        return pd.DataFrame(columns=["price_close", "volume"])
    bars = bars.set_index("ts")
    resampled = bars.resample(FREQ_MAP[freq]).agg({"c": "last", "v": "sum"}).dropna(subset=["c"])
    resampled = resampled.rename(columns={"c": "price_close", "v": "volume"})
    resampled["returns"] = np.log(resampled["price_close"]).diff()
    return resampled.reset_index()


def _bucket_sentiment_weight(post_collected_at: datetime, now: datetime, engagement: int) -> float:
    """Weight for sentiment aggregation (same logic as calculate_weighted_sentiment)."""
    hours_old = max(0.0, (now - post_collected_at).total_seconds() / 3600.0)
    time_weight = exp(-hours_old / 24.0)
    engagement_weight = log10(engagement + 1)
    return engagement_weight * time_weight


def build_dataset(
    symbol: str,
    start: datetime,
    end: datetime,
    freq: Freq,
    *,
    posts: list,
    parquet_root: str,
) -> CausalDataset | InsufficientDataResult:
    """Build aligned causal dataset from Reddit posts and intraday bars.

    Args:
        symbol: Stock symbol.
        start: Start of analysis window (UTC).
        end: End of analysis window (UTC).
        freq: Bucket frequency: "15min", "1h", or "1d".
        posts: Iterable of posts with .collected_at, .title, .upvotes, .comments.
        parquet_root: Root path for Parquet feature store.

    Returns:
        CausalDataset with aligned df, or InsufficientDataResult if too few buckets.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    else:
        end = end.astimezone(timezone.utc)

    bars = read_bars(parquet_root, symbol, start, end)
    if bars.empty:
        return InsufficientDataResult(
            symbol=symbol,
            freq=freq,
            reason="no_price_data",
            buckets_available=0,
            min_required=_min_buckets(freq),
        )

    resampled = _resample_bars(bars, freq)
    if resampled.empty:
        return InsufficientDataResult(
            symbol=symbol,
            freq=freq,
            reason="no_price_data_after_resample",
            buckets_available=0,
            min_required=_min_buckets(freq),
        )

    n_buckets = len(resampled)
    min_req = _min_buckets(freq)
    if n_buckets < min_req:
        return InsufficientDataResult(
            symbol=symbol,
            freq=freq,
            reason="insufficient_buckets",
            buckets_available=n_buckets,
            min_required=min_req,
        )

    # Build time index from resampled price data
    resampled = resampled.rename(columns={"ts": "bucket"})
    bucket_starts = resampled["bucket"].tolist()

    # Assign each post to a bucket (collected_at must fall inside bucket)
    # Use floor to find bucket: bucket_start <= collected_at < bucket_start + period
    period_map = {"15min": "15min", "1h": "1h", "1d": "1D"}
    period = period_map[freq]

    mentions_per_bucket: dict[pd.Timestamp, int] = {}
    sentiment_weighted_per_bucket: dict[pd.Timestamp, float] = {}
    weight_per_bucket: dict[pd.Timestamp, float] = {}

    for bucket_ts in bucket_starts:
        mentions_per_bucket[bucket_ts] = 0
        sentiment_weighted_per_bucket[bucket_ts] = 0.0
        weight_per_bucket[bucket_ts] = 0.0

    for post in posts:
        collected_at = post.collected_at
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        else:
            collected_at = collected_at.astimezone(timezone.utc)

        if collected_at < start or collected_at > end:
            continue

        collected_ts = pd.Timestamp(collected_at)
        bucket_ts = collected_ts.floor(period)
        if bucket_ts not in mentions_per_bucket:
            continue

        sentiment = analyze_post_sentiment(post.title)
        engagement = post.upvotes + post.comments + 1
        weight = _bucket_sentiment_weight(collected_at, collected_at, engagement)

        mentions_per_bucket[bucket_ts] += 1
        sentiment_weighted_per_bucket[bucket_ts] += sentiment * weight
        weight_per_bucket[bucket_ts] += weight

    # Build final df aligned to price buckets
    resampled["mentions"] = resampled["bucket"].map(lambda t: mentions_per_bucket.get(t, 0))
    sentiment_mean = []
    for t in resampled["bucket"]:
        w = weight_per_bucket.get(t, 0.0)
        sw = sentiment_weighted_per_bucket.get(t, 0.0)
        sentiment_mean.append(sw / w if w > 0 else 0.0)
    resampled["sentiment_mean"] = sentiment_mean

    result_df = resampled[["bucket", "mentions", "sentiment_mean", "price_close", "returns"]].copy()
    result_df = result_df.set_index("bucket")
    result_df.index.name = None

    return CausalDataset(
        df=result_df,
        symbol=symbol,
        freq=freq,
        start_utc=result_df.index.min().to_pydatetime(),
        end_utc=result_df.index.max().to_pydatetime(),
        sample_size=len(result_df),
    )

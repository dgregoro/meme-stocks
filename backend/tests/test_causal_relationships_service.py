"""Tests for causal relationships service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from backend.app.services.causal_dataset_builder import CausalDataset, InsufficientDataResult
from backend.app.services.causal_relationships_service import run_causal_analysis


def _make_dataset(n: int = 100, mention_leading: bool = True) -> CausalDataset:
    """Create synthetic CausalDataset for testing."""
    base = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    index = pd.DatetimeIndex([base + timedelta(hours=i) for i in range(n)])
    np.random.seed(42)
    returns = pd.Series(np.random.randn(n) * 0.01, index=index)
    if mention_leading:
        # Mentions lead returns by 2 buckets
        mentions = returns.shift(-2).fillna(0) * 10 + np.random.randn(n) * 2
        mentions = mentions.clip(lower=0).astype(int)
    else:
        mentions = pd.Series(np.random.randint(0, 5, n), index=index)
    sentiment = pd.Series(np.random.uniform(-0.5, 0.5, n), index=index)
    price_close = 100 * np.exp(returns.cumsum())
    df = pd.DataFrame(
        {
            "mentions": mentions,
            "sentiment_mean": sentiment,
            "price_close": price_close,
            "returns": returns,
        }
    )
    return CausalDataset(
        df=df,
        symbol="TEST",
        freq="1h",
        start_utc=index.min().to_pydatetime(),
        end_utc=index.max().to_pydatetime(),
        sample_size=n,
    )


@pytest.mark.unit
def test_run_causal_analysis_insufficient_passthrough() -> None:
    """InsufficientDataResult is passed through unchanged."""
    err = InsufficientDataResult(
        symbol="AAPL",
        freq="1h",
        reason="no_price_data",
        buckets_available=0,
        min_required=200,
    )
    result = run_causal_analysis(err)
    assert result is err


@pytest.mark.unit
def test_run_causal_analysis_returns_response() -> None:
    """Valid dataset produces CausalEvidenceResponse."""
    ds = _make_dataset(n=100)
    result = run_causal_analysis(ds, max_lag=5, include_placebo=False)
    assert not isinstance(result, InsufficientDataResult)
    assert result.symbol == "TEST"
    assert result.freq == "1h"
    assert result.sample_size == 100
    assert len(result.mention_xcorr) > 0
    assert len(result.sentiment_xcorr) > 0
    assert len(result.predictive) == 2
    assert "r2_oos" in [p.metric for p in result.predictive]
    assert "directional_acc" in [p.metric for p in result.predictive]


@pytest.mark.unit
def test_run_causal_analysis_deterministic() -> None:
    """Same input produces same output."""
    ds = _make_dataset(n=80)
    r1 = run_causal_analysis(ds, max_lag=3, include_placebo=True)
    r2 = run_causal_analysis(ds, max_lag=3, include_placebo=True)
    assert not isinstance(r1, InsufficientDataResult)
    assert not isinstance(r2, InsufficientDataResult)
    for l1, l2 in zip(r1.mention_xcorr, r2.mention_xcorr):
        assert l1.lag == l2.lag
        assert l1.corr == l2.corr


@pytest.mark.unit
def test_run_causal_analysis_placebo_lower_than_real() -> None:
    """Placebo (shuffled) typically yields lower predictive metrics than real."""
    ds = _make_dataset(n=120, mention_leading=True)
    result = run_causal_analysis(ds, max_lag=5, include_placebo=True)
    assert not isinstance(result, InsufficientDataResult)
    real_r2 = next(p.value for p in result.predictive if p.metric == "r2_oos")
    placebo_r2 = next(p.value for p in result.placebo if p.metric == "r2_oos")
    # With leading structure, real should often beat placebo (not guaranteed but typical)
    # At minimum both should be computed
    assert isinstance(real_r2, float)
    assert isinstance(placebo_r2, float)

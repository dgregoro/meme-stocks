"""Lead-lag evidence analysis: cross-correlation, predictive regression, placebo.

Labels outputs as 'lead-lag evidence' — does not claim true causality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

from backend.app.services.causal_dataset_builder import CausalDataset, InsufficientDataResult


@dataclass(frozen=True)
class LagCorrelation:
    """Correlation at a specific lag (positive lag = predictor leads returns)."""

    lag: int
    corr: float
    n: int


@dataclass(frozen=True)
class PredictiveResult:
    """Predictive metric from out-of-sample regression."""

    metric: str
    value: float


@dataclass(frozen=True)
class PlaceboResult:
    """Placebo test result (shuffled predictor)."""

    metric: str
    value: float


@dataclass(frozen=True)
class CausalEvidenceResponse:
    """Response from lead-lag evidence analysis."""

    symbol: str
    freq: str
    start_utc: str
    end_utc: str
    sample_size: int
    mention_xcorr: list[LagCorrelation]
    sentiment_xcorr: list[LagCorrelation]
    predictive: list[PredictiveResult]
    placebo: list[PlaceboResult]
    notes: list[str] = field(default_factory=list)


def _cross_corr_series(
    x: pd.Series,
    y: pd.Series,
    max_lag: int,
) -> list[LagCorrelation]:
    """Compute Spearman correlation at each lag. Positive lag = x leads y."""
    results: list[LagCorrelation] = []
    for lag in range(-max_lag, max_lag + 1):
        # shift(lag): positive lag = x leads y (past x vs current y)
        x_shifted = x.shift(lag)
        y_aligned = y
        valid = x_shifted.notna() & y_aligned.notna()
        if valid.sum() < 10:
            continue
        r, _ = spearmanr(x_shifted[valid], y_aligned[valid])
        if np.isnan(r):
            r = 0.0
        results.append(LagCorrelation(lag=lag, corr=float(r), n=int(valid.sum())))
    return results


def _predictive_metrics(
    mentions: pd.Series,
    sentiment: pd.Series,
    returns: pd.Series,
    max_lag: int,
    n_splits: int = 5,
) -> list[PredictiveResult]:
    """Ridge regression with time-series split; report OOS R² and directional accuracy."""
    df = pd.DataFrame({"mentions": mentions, "sentiment": sentiment, "returns": returns})
    for lag in range(1, max_lag + 1):
        df[f"mentions_lag{lag}"] = df["mentions"].shift(lag)
        df[f"sentiment_lag{lag}"] = df["sentiment"].shift(lag)
    feature_cols = [f"mentions_lag{i}" for i in range(1, max_lag + 1)] + [
        f"sentiment_lag{i}" for i in range(1, max_lag + 1)
    ]

    df = df.dropna(subset=["returns"])
    if len(df) < 20:
        return [
            PredictiveResult("r2_oos", 0.0),
            PredictiveResult("directional_acc", 0.0),
        ]

    X = df[feature_cols].fillna(0)
    y = df["returns"]

    tscv = TimeSeriesSplit(n_splits=min(n_splits, len(df) // 4))
    r2_scores: list[float] = []
    dir_acc_scores: list[float] = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        model = Ridge(alpha=1.0, random_state=42)
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        ss_res = np.sum((y_test - pred) ** 2)
        ss_tot = np.sum((y_test - y_test.mean()) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r2_scores.append(r2)
        dir_acc = np.mean(np.sign(pred) == np.sign(y_test.values))
        dir_acc_scores.append(dir_acc)

    return [
        PredictiveResult("r2_oos", float(np.mean(r2_scores))),
        PredictiveResult("directional_acc", float(np.mean(dir_acc_scores))),
    ]


def _placebo_metrics(
    mentions: pd.Series,
    sentiment: pd.Series,
    returns: pd.Series,
    max_lag: int,
    n_splits: int = 5,
    random_state: int = 42,
) -> list[PlaceboResult]:
    """Shuffle predictor series and re-run predictive metrics; should drop materially."""
    rng = np.random.default_rng(random_state)
    mentions_shuf = mentions.iloc[rng.permutation(len(mentions))].values
    mentions_shuf = pd.Series(mentions_shuf, index=mentions.index)
    sentiment_shuf = sentiment.iloc[rng.permutation(len(sentiment))].values
    sentiment_shuf = pd.Series(sentiment_shuf, index=sentiment.index)

    pred_results = _predictive_metrics(mentions_shuf, sentiment_shuf, returns, max_lag, n_splits)
    return [
        PlaceboResult(m.metric, m.value) for m in pred_results
    ]


def run_causal_analysis(
    dataset_or_error: Union[CausalDataset, InsufficientDataResult],
    max_lag: int = 12,
    include_placebo: bool = True,
) -> CausalEvidenceResponse | InsufficientDataResult:
    """Run lead-lag evidence analysis.

    Args:
        dataset_or_error: Output from build_dataset.
        max_lag: Maximum lag for cross-correlation and regression features.
        include_placebo: Whether to run placebo (shuffled) test.

    Returns:
        CausalEvidenceResponse with results, or InsufficientDataResult passed through.
    """
    if isinstance(dataset_or_error, InsufficientDataResult):
        return dataset_or_error

    ds = dataset_or_error
    df = ds.df.copy()

    if "returns" not in df.columns or df["returns"].notna().sum() < 10:
        return InsufficientDataResult(
            symbol=ds.symbol,
            freq=ds.freq,
            reason="insufficient_returns",
            buckets_available=len(df),
            min_required=10,
        )

    mentions = df["mentions"]
    sentiment = df["sentiment_mean"]
    returns = df["returns"].dropna()

    mention_xcorr = _cross_corr_series(mentions, returns, max_lag)
    sentiment_xcorr = _cross_corr_series(sentiment, returns, max_lag)

    predictive = _predictive_metrics(mentions, sentiment, returns, max_lag)

    placebo: list[PlaceboResult] = []
    if include_placebo:
        placebo = _placebo_metrics(mentions, sentiment, returns, max_lag)
        notes: list[str] = []
        for pr in predictive:
            pb = next((p for p in placebo if p.metric == pr.metric), None)
            if pb and abs(pr.value - pb.value) < 0.01:
                notes.append(f"Placebo {pr.metric} close to real; evidence may be weak")
        if not notes:
            notes.append("Placebo test: shuffled predictors yield lower metrics (expected)")
    else:
        notes = ["Placebo test skipped"]

    return CausalEvidenceResponse(
        symbol=ds.symbol,
        freq=ds.freq,
        start_utc=ds.start_utc.isoformat(),
        end_utc=ds.end_utc.isoformat(),
        sample_size=ds.sample_size,
        mention_xcorr=mention_xcorr,
        sentiment_xcorr=sentiment_xcorr,
        predictive=predictive,
        placebo=placebo,
        notes=notes,
    )

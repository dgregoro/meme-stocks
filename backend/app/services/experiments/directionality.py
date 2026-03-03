"""Directionality sanity check: mentions lead returns vs returns lead mentions.

Per CAUSAL_RESEARCH.md: Test which direction appears stronger before modeling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class DirectionalityResult:
    """Results from directionality experiment."""

    mentions_lead_returns_corr: float | None
    mentions_lead_returns_n: int
    returns_lead_mentions_corr: float | None
    returns_lead_mentions_n: int


def _load_dataset(path: str) -> pd.DataFrame:
    """Load CSV dataset, ensure required columns exist."""
    df = pd.read_csv(path)
    required = {"symbol", "trading_day", "mention_count", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    # Find label column (y_fwd_return_N)
    label_cols = [c for c in df.columns if c.startswith("y_fwd_return_")]
    if not label_cols:
        raise ValueError("Dataset missing y_fwd_return_N column")
    return df


def run_directionality(
    dataset_path: str,
    k: int = 5,
    h: int = 1,
) -> DirectionalityResult:
    """Run directionality experiment: mentions→returns vs returns→mentions.

    - mentions_lead_returns: correlate lagged mentions (t-k..t-1) with fwd_return at t
    - returns_lead_mentions: correlate lagged returns (t-k..t-1) with mention_count at t+h

    Uses horizon h to select y_fwd_return_{h} and for the returns→mentions lookahead.
    """
    df = _load_dataset(dataset_path)
    df["trading_day"] = pd.to_datetime(df["trading_day"]).dt.date

    # Determine horizon column
    label_col: str
    if f"y_fwd_return_{h}" in df.columns:
        label_col = f"y_fwd_return_{h}"
    else:
        label_cols = [c for c in df.columns if c.startswith("y_fwd_return_")]
        if not label_cols:
            raise ValueError("Dataset has no y_fwd_return_N column")
        label_col = label_cols[0]
    df["_fwd_ret"] = pd.to_numeric(df[label_col], errors="coerce")

    # Compute same-day return (close[D]/close[D-1]-1) for returns_lead
    df = df.sort_values(["symbol", "trading_day"])
    df["return_1d"] = df.groupby("symbol")["close"].pct_change()

    # Build lagged features per symbol
    results_mentions_lead: list[tuple[float, float]] = []
    results_returns_lead: list[tuple[float, float]] = []

    for symbol, grp in df.groupby("symbol"):
        grp = grp.sort_values("trading_day").reset_index(drop=True)
        if len(grp) < k + 2:
            continue

        # Lagged mention_count (t-1, t-2, ..., t-k)
        for i in range(k, len(grp)):
            lags = grp.iloc[i - k : i]["mention_count"].values
            if np.any(np.isnan(lags)):
                continue
            y = grp["_fwd_ret"].iloc[i]
            if pd.isna(y):
                continue
            x = np.mean(lags)
            results_mentions_lead.append((x, y))

        # Lagged returns vs future mention_count
        for i in range(k, len(grp) - h):
            if i + h >= len(grp):
                continue
            lag_returns = grp.iloc[i - k : i]["return_1d"].values
            if np.any(np.isnan(lag_returns)) or np.any(np.isinf(lag_returns)):
                continue
            future_mentions = grp.iloc[i + h]["mention_count"]
            if pd.isna(future_mentions):
                continue
            x = np.mean(lag_returns)
            results_returns_lead.append((x, future_mentions))

    def _corr(pairs: list[tuple[float, float]]) -> tuple[float | None, int]:
        if len(pairs) < 10:
            return None, len(pairs)
        xs = np.array([p[0] for p in pairs])
        ys = np.array([p[1] for p in pairs])
        c = np.corrcoef(xs, ys)[0, 1]
        return float(c) if not np.isnan(c) else None, len(pairs)

    m_corr, m_n = _corr(results_mentions_lead)
    r_corr, r_n = _corr(results_returns_lead)

    return DirectionalityResult(
        mentions_lead_returns_corr=m_corr,
        mentions_lead_returns_n=m_n,
        returns_lead_mentions_corr=r_corr,
        returns_lead_mentions_n=r_n,
    )

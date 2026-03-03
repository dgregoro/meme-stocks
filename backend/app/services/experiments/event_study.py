"""Event study: mention spike days vs forward returns.

Per CAUSAL_RESEARCH.md: Define spike days (mention_count > rolling_mean + N*std
or percentile threshold), compute average forward returns for spike vs non-spike.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class EventStudyResult:
    """Results from event study experiment."""

    spike_mean_fwd_return: float | None
    spike_n: int
    non_spike_mean_fwd_return: float | None
    non_spike_n: int
    spread: float | None  # spike - non_spike


def _load_dataset(path: str) -> pd.DataFrame:
    """Load CSV dataset."""
    df = pd.read_csv(path)
    required = {"symbol", "trading_day", "mention_count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    label_cols = [c for c in df.columns if c.startswith("y_fwd_return_")]
    if not label_cols:
        raise ValueError("Dataset missing y_fwd_return_N column")
    return df


def run_event_study(
    dataset_path: str,
    window: int = 20,
    threshold: str = "p95",
    horizon: int = 5,
) -> EventStudyResult:
    """Run event study: spike vs non-spike forward returns.

    Spike definition:
    - If threshold starts with 'p': percentile (e.g. p95 = 95th percentile)
    - Else: rolling_mean + N*rolling_std (N parsed from threshold)
    """
    df = _load_dataset(dataset_path)
    df["trading_day"] = pd.to_datetime(df["trading_day"]).dt.date

    label_col = f"y_fwd_return_{horizon}"
    if label_col not in df.columns:
        label_col = [c for c in df.columns if c.startswith("y_fwd_return_")][0]
    df["_fwd_ret"] = pd.to_numeric(df[label_col], errors="coerce")

    spike_returns: list[float] = []
    non_spike_returns: list[float] = []

    for symbol, grp in df.groupby("symbol"):
        grp = grp.sort_values("trading_day").reset_index(drop=True)
        if len(grp) < window + 1:
            continue

        ment = grp["mention_count"].values
        rolling_mean = pd.Series(ment).rolling(window, min_periods=window).mean().values
        rolling_std = pd.Series(ment).rolling(window, min_periods=window).std().values

        for i in range(window, len(grp)):
            m = ment[i]
            fwd = grp["_fwd_ret"].iloc[i]
            if pd.isna(fwd):
                continue
            rm = rolling_mean[i]
            rs = rolling_std[i] if not np.isnan(rolling_std[i]) and rolling_std[i] > 0 else 0.0

            if threshold.startswith("p"):
                pct = int(threshold[1:])
                thresh = np.percentile(ment[: i + 1], pct)
                is_spike = m >= thresh
            else:
                try:
                    n_sigma = float(threshold)
                except ValueError:
                    n_sigma = 2.0
                thresh = rm + n_sigma * rs if rs > 0 else rm
                is_spike = m >= thresh

            if is_spike:
                spike_returns.append(float(fwd))
            else:
                non_spike_returns.append(float(fwd))

    def _mean(vals: list[float]) -> float | None:
        if not vals:
            return None
        return float(np.mean(vals))

    sm = _mean(spike_returns)
    nm = _mean(non_spike_returns)
    spread = (sm - nm) if sm is not None and nm is not None else None

    return EventStudyResult(
        spike_mean_fwd_return=sm,
        spike_n=len(spike_returns),
        non_spike_mean_fwd_return=nm,
        non_spike_n=len(non_spike_returns),
        spread=spread,
    )

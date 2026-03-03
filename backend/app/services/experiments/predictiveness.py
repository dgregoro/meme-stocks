"""Granger-style predictiveness: baseline vs augmented features.

Per CAUSAL_RESEARCH.md: Compare baseline (past returns, volume, RSI) with
augmented (baseline + Reddit features). Time-based split only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.metrics import accuracy_score, mean_squared_error

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class PredictivenessResult:
    """Results from predictiveness experiment."""

    baseline_direction_accuracy: float | None
    augmented_direction_accuracy: float | None
    baseline_ridge_rmse: float | None
    augmented_ridge_rmse: float | None
    n_train: int
    n_test: int


def _load_dataset(path: str) -> pd.DataFrame:
    """Load CSV dataset."""
    df = pd.read_csv(path)
    required = {"symbol", "trading_day", "mention_count", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    label_cols = [c for c in df.columns if c.startswith("y_fwd_return_")]
    if not label_cols:
        raise ValueError("Dataset missing y_fwd_return_N column")
    return df


def run_predictiveness(
    dataset_path: str,
    horizon: int = 5,
    split_date: str | None = None,
) -> PredictivenessResult:
    """Run predictiveness: baseline vs augmented out-of-sample.

    Uses time-based split: train on dates < split_date, test on dates >= split_date.
    If split_date not provided, uses 80% of date range.
    """
    if not HAS_SKLEARN:
        raise ImportError("scikit-learn is required for predictiveness experiment. pip install scikit-learn")

    df = _load_dataset(dataset_path)
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    df = df.sort_values(["symbol", "trading_day"]).reset_index(drop=True)

    label_col = f"y_fwd_return_{horizon}"
    if label_col not in df.columns:
        label_col = [c for c in df.columns if c.startswith("y_fwd_return_")][0]
    df["_fwd_ret"] = pd.to_numeric(df[label_col], errors="coerce")

    # Same-day features (no look-ahead)
    df["return_1d"] = df.groupby("symbol")["close"].pct_change()
    # Simplified RSI proxy: use return sign if available (or 0)
    df["rsi_proxy"] = np.clip((df["return_1d"] + 0.02) * 25, 0, 100)

    # Reddit features (same-day, no future)
    reddit_cols = ["mention_count", "unique_authors", "upvote_weighted_mentions"]
    base_cols = ["return_1d", "volume", "rsi_proxy"]
    aug_cols = base_cols + [c for c in reddit_cols if c in df.columns]

    valid = df.dropna(subset=["_fwd_ret", "return_1d", "volume"] + aug_cols, how="any")
    if len(valid) < 50:
        return PredictivenessResult(
            baseline_direction_accuracy=None,
            augmented_direction_accuracy=None,
            baseline_ridge_rmse=None,
            augmented_ridge_rmse=None,
            n_train=len(valid),
            n_test=0,
        )

    if split_date:
        split_d = pd.to_datetime(split_date).date()
        train = valid[valid["trading_day"].dt.date < split_d]
        test = valid[valid["trading_day"].dt.date >= split_d]
    else:
        dates = valid["trading_day"].unique()
        idx = int(len(dates) * 0.8)
        split_d = dates[idx] if idx < len(dates) else dates[-1]
        train = valid[valid["trading_day"] < split_d]
        test = valid[valid["trading_day"] >= split_d]

    if len(train) < 20 or len(test) < 10:
        return PredictivenessResult(
            baseline_direction_accuracy=None,
            augmented_direction_accuracy=None,
            baseline_ridge_rmse=None,
            augmented_ridge_rmse=None,
            n_train=len(train),
            n_test=len(test),
        )

    y_train = train["_fwd_ret"].values
    y_test = test["_fwd_ret"].values
    y_dir_train = (y_train > 0).astype(int)
    y_dir_test = (y_test > 0).astype(int)

    X_base_train = train[base_cols].fillna(0).values
    X_base_test = test[base_cols].fillna(0).values
    X_aug_train = train[aug_cols].fillna(0).values
    X_aug_test = test[aug_cols].fillna(0).values

    baseline_acc = None
    augmented_acc = None
    baseline_rmse = None
    augmented_rmse = None

    # Direction (logistic)
    lr_base = LogisticRegression(max_iter=500, random_state=42)
    lr_base.fit(X_base_train, y_dir_train)
    baseline_acc = float(accuracy_score(y_dir_test, lr_base.predict(X_base_test)))

    lr_aug = LogisticRegression(max_iter=500, random_state=42)
    lr_aug.fit(X_aug_train, y_dir_train)
    augmented_acc = float(accuracy_score(y_dir_test, lr_aug.predict(X_aug_test)))

    # Magnitude (ridge)
    ridge_base = Ridge(alpha=1.0, random_state=42)
    ridge_base.fit(X_base_train, y_train)
    baseline_rmse = float(np.sqrt(mean_squared_error(y_test, ridge_base.predict(X_base_test))))

    ridge_aug = Ridge(alpha=1.0, random_state=42)
    ridge_aug.fit(X_aug_train, y_train)
    augmented_rmse = float(np.sqrt(mean_squared_error(y_test, ridge_aug.predict(X_aug_test))))

    return PredictivenessResult(
        baseline_direction_accuracy=baseline_acc,
        augmented_direction_accuracy=augmented_acc,
        baseline_ridge_rmse=baseline_rmse,
        augmented_ridge_rmse=augmented_rmse,
        n_train=len(train),
        n_test=len(test),
    )

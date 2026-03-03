"""Parquet feature store reader for minute bars (partitioned by symbol/date)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

# Columns we need for causal analysis
BAR_COLUMNS = ["ts", "c", "v"]


def read_bars(
    root: str,
    symbol: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Read minute bars for a symbol within a datetime range.

    Uses pyarrow.dataset to read partitions under root/bars/symbol=SYM/date=YYYY-MM-DD/.
    Filters by ts between [start, end]. Returns df with ts, c, v, sorted by ts, UTC-aware.

    Args:
        root: Feature store root (e.g. data/intraday).
        symbol: Stock symbol (e.g. AAPL).
        start: Start datetime (inclusive), UTC.
        end: End datetime (inclusive), UTC.

    Returns:
        DataFrame with columns ts, c, v (close, volume). Empty if no data.
    """
    root_path = Path(root)
    bars_dir = root_path / "bars"

    if not bars_dir.exists():
        return _empty_df()

    symbol_dir = bars_dir / f"symbol={symbol}"
    if not symbol_dir.exists():
        return _empty_df()

    # Normalize to UTC
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    else:
        end = end.astimezone(timezone.utc)

    try:
        dataset = ds.dataset(str(symbol_dir), format="parquet")
        table = dataset.to_table(columns=BAR_COLUMNS)
    except Exception:
        return _empty_df()

    if table.num_rows == 0:
        return _empty_df()

    df = table.to_pandas()

    if "ts" not in df.columns:
        return _empty_df()

    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    # Filter by range (push-down not guaranteed across pyarrow versions)
    mask = (df["ts"] >= start) & (df["ts"] <= end)
    df = df.loc[mask].sort_values("ts").reset_index(drop=True)

    return df[BAR_COLUMNS]


def _empty_df() -> pd.DataFrame:
    """Return empty DataFrame with correct schema."""
    return pd.DataFrame(columns=BAR_COLUMNS)

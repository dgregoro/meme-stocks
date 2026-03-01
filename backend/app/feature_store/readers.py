"""Read minute bars from the Parquet feature store for training."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def _empty_bars_table() -> pa.Table:
    """Return an empty table with the bar schema."""
    return pa.table(
        {
            "ts": pa.array([], type=pa.timestamp("us", tz="UTC")),
            "o": pa.array([], type=pa.float64()),
            "h": pa.array([], type=pa.float64()),
            "l": pa.array([], type=pa.float64()),
            "c": pa.array([], type=pa.float64()),
            "v": pa.array([], type=pa.float64()),
            "n": pa.array([], type=pa.int64()),
            "vw": pa.array([], type=pa.float64()),
            "source": pa.array([], type=pa.string()),
        }
    )


def read_bars(
    root: str,
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    strict_reads: bool = False,
) -> pa.Table:
    """Read bars for symbol between start and end (inclusive), sorted by ts.

    Determines date partitions that overlap [start, end], reads only those
    files, and filters ts between start/end. All timestamps in UTC.

    If a partition file is unreadable: logs a warning with path and exception,
    increments skipped count, and skips the file. When strict_reads is True,
    raises the first read error instead of skipping (no silent partial reads).
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start > end:
        return _empty_bars_table()

    base = Path(root) / "bars" / f"symbol={symbol}"
    if not base.exists():
        return _empty_bars_table()

    # Date range for partition scan
    start_date = start.date().strftime("%Y-%m-%d")
    end_date = end.date().strftime("%Y-%m-%d")
    date_dirs = sorted(base.glob("date=*"))
    tables: list[pa.Table] = []
    skipped_count = 0
    for d in date_dirs:
        if not d.is_dir():
            continue
        part = d.name.replace("date=", "")
        if part < start_date or part > end_date:
            continue
        for f in d.glob("*.parquet"):
            try:
                t = pq.read_table(f)
                tables.append(t)
            except Exception as exc:  # nosec B112
                skipped_count += 1
                logger.warning(
                    "Skipped unreadable Parquet partition: path=%s error_type=%s message=%s",
                    str(f),
                    type(exc).__name__,
                    str(exc),
                )
                if strict_reads:
                    raise

    if skipped_count > 0:
        logger.warning(
            "read_bars partial read: symbol=%s skipped_files=%s (check logs for paths)",
            symbol,
            skipped_count,
        )

    if not tables:
        return _empty_bars_table()

    combined = pa.concat_tables(tables)
    ts_col = combined.column("ts")
    start_scalar = pa.scalar(start, type=pa.timestamp("us", tz="UTC"))
    end_scalar = pa.scalar(end, type=pa.timestamp("us", tz="UTC"))
    mask = pa.compute.and_(
        pa.compute.greater_equal(ts_col, start_scalar),
        pa.compute.less_equal(ts_col, end_scalar),
    )
    filtered = combined.filter(mask)
    # Sort by ts
    indices = pa.compute.sort_indices(filtered.column("ts"))
    return filtered.take(indices)

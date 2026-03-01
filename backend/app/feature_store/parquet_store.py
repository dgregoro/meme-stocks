"""Parquet feature store for minute bars (append-only, partitioned by symbol/date)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

# Schema for one bar row (UTC ts, OHLCV, optional n/vw, source)
BAR_SCHEMA = pa.schema(
    [
        ("ts", pa.timestamp("us", tz="UTC")),
        ("o", pa.float64()),
        ("h", pa.float64()),
        ("l", pa.float64()),
        ("c", pa.float64()),
        ("v", pa.float64()),  # int64 acceptable but float64 for consistency with optional vw
        ("n", pa.int64()),
        ("vw", pa.float64()),
        ("source", pa.string()),
    ]
)

SOURCE_DEFAULT = "alpaca"


def _parse_ts(value: str | datetime) -> datetime:
    """Parse Alpaca 't' or datetime to UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    # ISO string
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bar_dict_to_row(bar: dict, source: str = SOURCE_DEFAULT) -> tuple:
    """Convert one Alpaca-style bar dict to a tuple matching BAR_SCHEMA."""
    ts = _parse_ts(bar["t"])
    o = float(bar["o"])
    h = float(bar["h"])
    l_ = float(bar["l"])
    c = float(bar["c"])
    v = float(bar.get("v", 0))
    n = int(bar.get("n", 0))
    vw = float(bar.get("vw", 0.0))
    return (ts, o, h, l_, c, v, n, vw, source)


def _bars_for_symbol_to_table(symbol: str, bars: list[dict], source: str = SOURCE_DEFAULT) -> pa.Table:
    """Build a PyArrow Table for one symbol's bars, sorted by ts."""
    if not bars:
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
    rows = [_bar_dict_to_row(b, source) for b in bars]
    rows.sort(key=lambda r: r[0])
    arrays = [
        pa.array([r[0] for r in rows], type=pa.timestamp("us", tz="UTC")),
        pa.array([r[1] for r in rows], type=pa.float64()),
        pa.array([r[2] for r in rows], type=pa.float64()),
        pa.array([r[3] for r in rows], type=pa.float64()),
        pa.array([r[4] for r in rows], type=pa.float64()),
        pa.array([r[5] for r in rows], type=pa.float64()),
        pa.array([r[6] for r in rows], type=pa.int64()),
        pa.array([r[7] for r in rows], type=pa.float64()),
        pa.array([r[8] for r in rows], type=pa.string()),
    ]
    return pa.table(
        [arrays[0], arrays[1], arrays[2], arrays[3], arrays[4], arrays[5], arrays[6], arrays[7], arrays[8]],
        names=["ts", "o", "h", "l", "c", "v", "n", "vw", "source"],
    )


class ParquetFeatureStore:
    """Writes minute bars to root/bars/symbol=SYM/date=YYYY-MM-DD/part-<uuid>.parquet."""

    def __init__(self, root: str, source: str = SOURCE_DEFAULT) -> None:
        self._root = Path(root)
        self._source = source

    def write_bars(self, bars_by_symbol: dict[str, list[dict]]) -> int:
        """Write bars keyed by symbol. Each list is Alpaca-style bar dicts.
        Appends new part files per symbol/date. Returns total rows written.
        """
        total = 0
        for symbol, bars in bars_by_symbol.items():
            if not bars:
                continue
            table = _bars_for_symbol_to_table(symbol, bars, self._source)
            if table.num_rows == 0:
                continue
            # Partition by symbol and date (from ts)
            ts_col = table.column("ts")
            dates_seen: set[str] = set()
            for i in range(table.num_rows):
                dt = ts_col[i].as_py()
                if dt is not None:
                    dates_seen.add(dt.strftime("%Y-%m-%d"))
            # Write one file per (symbol, date) that has data in this chunk
            for date_str in sorted(dates_seen):
                indices = [i for i in range(table.num_rows) if ts_col[i].as_py().strftime("%Y-%m-%d") == date_str]
                if not indices:
                    continue
                sub = table.take(indices)
                dir_path = self._root / "bars" / f"symbol={symbol}" / f"date={date_str}"
                dir_path.mkdir(parents=True, exist_ok=True)
                part_path = dir_path / f"part-{uuid.uuid4().hex}.parquet"
                pq.write_table(sub, part_path)
                total += sub.num_rows
        return total

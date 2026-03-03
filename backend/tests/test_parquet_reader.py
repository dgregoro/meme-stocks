"""Tests for Parquet feature store reader."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from backend.app.feature_store.parquet_reader import read_bars


def _write_test_parquet(path: Path, rows: list[tuple]) -> None:
    """Write a minimal parquet file with ts, c, v columns."""
    if not rows:
        return
    arrays = [
        pa.array([r[0] for r in rows], type=pa.timestamp("us", tz="UTC")),
        pa.array([r[1] for r in rows], type=pa.float64()),
        pa.array([r[2] for r in rows], type=pa.float64()),
    ]
    # Full schema for compatibility with writer
    full_arrays = arrays + [
        pa.array([r[1] for r in rows], type=pa.float64()),  # o
        pa.array([r[1] for r in rows], type=pa.float64()),  # h
        pa.array([r[1] for r in rows], type=pa.float64()),  # l
        pa.array([0 for _ in rows], type=pa.int64()),  # n
        pa.array([0.0 for _ in rows], type=pa.float64()),  # vw
        pa.array(["test" for _ in rows], type=pa.string()),  # source
    ]
    table = pa.table(
        {
            "ts": full_arrays[0],
            "o": full_arrays[3],
            "h": full_arrays[4],
            "l": full_arrays[5],
            "c": full_arrays[1],
            "v": full_arrays[2],
            "n": full_arrays[6],
            "vw": full_arrays[7],
            "source": full_arrays[8],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


@pytest.mark.unit
def test_read_bars_empty_when_no_dir(tmp_path: Path) -> None:
    """Reading when root/bars does not exist returns empty df."""
    result = read_bars(str(tmp_path), "AAPL", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert result.empty
    assert list(result.columns) == ["ts", "c", "v"]


@pytest.mark.unit
def test_read_bars_empty_when_no_symbol(tmp_path: Path) -> None:
    """Reading when symbol dir does not exist returns empty df."""
    (tmp_path / "bars").mkdir()
    result = read_bars(str(tmp_path), "AAPL", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert result.empty


@pytest.mark.unit
def test_read_bars_single_partition(tmp_path: Path) -> None:
    """Reading works across a single date partition."""
    base = tmp_path / "bars" / "symbol=AAPL" / "date=2026-01-15"
    base.mkdir(parents=True)
    t1 = datetime(2026, 1, 15, 9, 31, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 15, 9, 32, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 15, 9, 33, tzinfo=timezone.utc)
    _write_test_parquet(base / "part-abc.parquet", [(t1, 100.0, 1000.0), (t2, 100.5, 1100.0), (t3, 101.0, 1200.0)])

    result = read_bars(
        str(tmp_path),
        "AAPL",
        datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )

    assert len(result) == 3
    assert list(result.columns) == ["ts", "c", "v"]
    assert result["c"].tolist() == [100.0, 100.5, 101.0]
    assert result["v"].tolist() == [1000.0, 1100.0, 1200.0]
    assert result["ts"].dt.tz is not None
    assert result["ts"].is_monotonic_increasing


@pytest.mark.unit
def test_read_bars_multiple_partitions(tmp_path: Path) -> None:
    """Reading works across multiple date partitions."""
    for date_str, ts_hour in [("2026-01-14", 15), ("2026-01-15", 9), ("2026-01-16", 9)]:
        base = tmp_path / "bars" / "symbol=TSLA" / f"date={date_str}"
        base.mkdir(parents=True)
        t = datetime(2026, int(date_str[5:7]), int(date_str[8:10]), ts_hour, 31, tzinfo=timezone.utc)
        _write_test_parquet(base / "part.parquet", [(t, 250.0, 5000.0)])

    result = read_bars(
        str(tmp_path),
        "TSLA",
        datetime(2026, 1, 14, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc),
    )

    assert len(result) == 3
    assert result["ts"].is_monotonic_increasing


@pytest.mark.unit
def test_read_bars_filters_by_range(tmp_path: Path) -> None:
    """Only rows within [start, end] are returned."""
    base = tmp_path / "bars" / "symbol=AAPL" / "date=2026-01-15"
    base.mkdir(parents=True)
    rows = [
        (datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc), 99.0, 900.0),
        (datetime(2026, 1, 15, 9, 45, tzinfo=timezone.utc), 100.0, 1000.0),
        (datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc), 101.0, 1100.0),
        (datetime(2026, 1, 15, 10, 15, tzinfo=timezone.utc), 102.0, 1200.0),
    ]
    _write_test_parquet(base / "part.parquet", rows)

    result = read_bars(
        str(tmp_path),
        "AAPL",
        datetime(2026, 1, 15, 9, 45, tzinfo=timezone.utc),
        datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )

    assert len(result) == 2
    assert result["c"].tolist() == [100.0, 101.0]


@pytest.mark.unit
def test_read_bars_naive_datetimes_normalized_to_utc(tmp_path: Path) -> None:
    """Naive start/end are interpreted as UTC."""
    base = tmp_path / "bars" / "symbol=AAPL" / "date=2026-01-15"
    base.mkdir(parents=True)
    t = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    _write_test_parquet(base / "part.parquet", [(t, 100.0, 1000.0)])

    result = read_bars(
        str(tmp_path),
        "AAPL",
        datetime(2026, 1, 15, 11, 0),  # naive
        datetime(2026, 1, 15, 13, 0),  # naive
    )

    assert len(result) == 1

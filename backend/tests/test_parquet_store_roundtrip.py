"""Roundtrip tests for Parquet feature store write and read."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.feature_store.parquet_store import ParquetFeatureStore
from backend.app.feature_store.readers import read_bars


@pytest.mark.unit
def test_parquet_roundtrip_two_symbols_two_dates() -> None:
    """Write a small bars dict for 2 symbols across 2 dates, read back and assert count/order."""
    with tempfile.TemporaryDirectory() as tmp:
        store = ParquetFeatureStore(tmp, source="alpaca")
        bars_by_symbol = {
            "AAPL": [
                {"t": "2026-03-01T09:30:00Z", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1000, "n": 10, "vw": 100.2},
                {"t": "2026-03-01T09:31:00Z", "o": 100.5, "h": 101.5, "l": 100.0, "c": 101.0, "v": 1100, "n": 12, "vw": 100.8},
                {"t": "2026-03-02T09:30:00Z", "o": 101.0, "h": 102.0, "l": 100.5, "c": 101.5, "v": 1200, "n": 15, "vw": 101.2},
            ],
            "GOOG": [
                {"t": "2026-03-01T09:30:00Z", "o": 150.0, "h": 151.0, "l": 149.0, "c": 150.5, "v": 2000, "n": 20, "vw": 150.2},
                {"t": "2026-03-02T09:31:00Z", "o": 150.5, "h": 152.0, "l": 150.0, "c": 151.0, "v": 2100, "n": 22, "vw": 150.8},
            ],
        }
        written = store.write_bars(bars_by_symbol)
        assert written == 5

        # Read AAPL for 2026-03-01
        start = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        table_aapl = read_bars(tmp, "AAPL", start, end)
        assert table_aapl.num_rows == 2
        assert table_aapl.column("ts")[0].as_py() <= table_aapl.column("ts")[1].as_py()
        assert table_aapl.column("c")[0].as_py() == 100.5
        assert table_aapl.column("c")[1].as_py() == 101.0

        # Read GOOG for full range
        start2 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        end2 = datetime(2026, 3, 3, 0, 0, 0, tzinfo=timezone.utc)
        table_goog = read_bars(tmp, "GOOG", start2, end2)
        assert table_goog.num_rows == 2
        assert table_goog.column("ts")[0].as_py() <= table_goog.column("ts")[1].as_py()

        # Read AAPL both days
        table_aapl_both = read_bars(tmp, "AAPL", start2, end2)
        assert table_aapl_both.num_rows == 3
        assert table_aapl_both.column("c")[2].as_py() == 101.5

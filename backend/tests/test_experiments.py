"""Tests for causal research experiment runners."""

from __future__ import annotations

import csv
import os
import tempfile
from datetime import date, timedelta

import pytest

from backend.app.services.experiments.directionality import run_directionality
from backend.app.services.experiments.event_study import run_event_study


def _make_minimal_dataset(path: str, n_rows: int = 50) -> None:
    """Write a minimal CSV with symbol, trading_day, mention_count, close, volume, y_fwd_return_5."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "symbol",
                "trading_day",
                "mention_count",
                "unique_authors",
                "total_upvotes",
                "total_comments",
                "upvote_weighted_mentions",
                "close",
                "volume",
                "y_fwd_return_5",
            ]
        )
        base = date(2026, 1, 1)
        for i in range(n_rows):
            d = base + timedelta(days=i)
            w.writerow(
                [
                    "GME",
                    d.isoformat(),
                    10 + (i % 5),
                    3,
                    50,
                    10,
                    1.5,
                    100.0 + i * 0.5,
                    1000 + i * 10,
                    0.01 * (i % 3 - 1),
                ]
            )


@pytest.mark.unit
def test_directionality_runs_on_dataset() -> None:
    """Directionality experiment completes without error on minimal dataset."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        _make_minimal_dataset(path, n_rows=40)
        result = run_directionality(dataset_path=path, k=3, h=1)
        assert result.mentions_lead_returns_n >= 0
        assert result.returns_lead_mentions_n >= 0
    finally:
        os.unlink(path)


@pytest.mark.unit
def test_directionality_raises_on_missing_columns() -> None:
    """Directionality raises ValueError when dataset lacks required columns."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("symbol,trading_day\nGME,2026-01-01\n")
        path = f.name
    try:
        with pytest.raises(ValueError, match="missing columns"):
            run_directionality(dataset_path=path)
    finally:
        os.unlink(path)


@pytest.mark.unit
def test_event_study_runs_on_dataset() -> None:
    """Event study completes without error on minimal dataset."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        path = f.name
    try:
        _make_minimal_dataset(path, n_rows=50)
        result = run_event_study(
            dataset_path=path,
            window=10,
            threshold="p95",
            horizon=5,
        )
        assert result.spike_n >= 0
        assert result.non_spike_n >= 0
    finally:
        os.unlink(path)

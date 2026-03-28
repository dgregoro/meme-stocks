"""Tests for start-window grouping in intraday ingestion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.intraday_ingestion_service import _group_symbols_by_start_window


@pytest.mark.unit
def test_group_symbols_by_start_window_separates_far_apart_starts() -> None:
    """Symbols with starts far apart form separate groups."""
    now = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
    start_by_symbol = {
        "AAPL": now - timedelta(minutes=10),
        "GOOG": now - timedelta(days=30),
    }

    groups = _group_symbols_by_start_window(start_by_symbol, max_span=timedelta(hours=1))

    assert len(groups) == 2
    assert any(g == ["GOOG"] for g in groups)
    assert any(g == ["AAPL"] for g in groups)


@pytest.mark.unit
def test_group_symbols_by_start_window_groups_close_starts() -> None:
    """Symbols with starts within max_span form one group."""
    now = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
    start_by_symbol = {
        "AAPL": now - timedelta(minutes=50),
        "MSFT": now - timedelta(minutes=20),
        "GOOG": now - timedelta(minutes=10),
    }

    groups = _group_symbols_by_start_window(start_by_symbol, max_span=timedelta(hours=1))

    assert len(groups) == 1
    assert set(groups[0]) == {"AAPL", "MSFT", "GOOG"}


@pytest.mark.unit
def test_group_symbols_by_start_window_creates_multiple_groups_when_needed() -> None:
    """When starts are separated, multiple groups are created."""
    now = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
    start_by_symbol = {
        "AAA": now - timedelta(hours=5),
        "BBB": now - timedelta(hours=4, minutes=10),
        "CCC": now - timedelta(hours=2),
        "DDD": now - timedelta(hours=1, minutes=10),
    }

    groups = _group_symbols_by_start_window(start_by_symbol, max_span=timedelta(hours=1))

    assert len(groups) >= 2
    for g in groups:
        starts = [start_by_symbol[s] for s in g]
        assert max(starts) - min(starts) <= timedelta(hours=1)


@pytest.mark.unit
def test_group_symbols_by_start_window_empty_returns_empty() -> None:
    """Empty input returns empty list."""
    assert _group_symbols_by_start_window({}, timedelta(hours=1)) == []

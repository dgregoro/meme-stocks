"""Tests for research_execution.walk_forward_harness (spec 020)."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.research_execution.walk_forward_harness import (
    run_walk_forward_windows,
)


@pytest.mark.unit
def test_three_windows_serial_success() -> None:
    windows = [
        (date(2020, 1, 1), date(2020, 1, 31)),
        (date(2020, 2, 1), date(2020, 2, 29)),
        (date(2020, 3, 1), date(2020, 3, 31)),
    ]
    n = {"count": 0}

    def cb(a: date, b: date) -> int:
        n["count"] += 1
        return n["count"]

    rows = run_walk_forward_windows(windows, cb)
    assert [r.metrics for r in rows] == [1, 2, 3]
    assert all(r.error is None for r in rows)


@pytest.mark.unit
def test_failure_isolated_non_strict() -> None:
    windows = [
        (date(2020, 1, 1), date(2020, 1, 10)),
        (date(2020, 2, 1), date(2020, 2, 10)),
        (date(2020, 3, 1), date(2020, 3, 10)),
    ]

    def cb(a: date, b: date) -> int:
        if a.month == 2:
            raise ValueError("boom")
        return a.month

    rows = run_walk_forward_windows(windows, cb, strict=False)
    assert rows[0].metrics == 1
    assert rows[0].error is None
    assert rows[1].metrics is None
    assert rows[1].error == "boom"
    assert rows[2].metrics == 3


@pytest.mark.unit
def test_strict_re_raises() -> None:
    windows = [
        (date(2020, 1, 1), date(2020, 1, 10)),
        (date(2020, 2, 1), date(2020, 2, 10)),
    ]

    def cb(a: date, b: date) -> int:
        if a.month == 2:
            raise RuntimeError("stop")
        return 1

    with pytest.raises(RuntimeError, match="stop"):
        run_walk_forward_windows(windows, cb, strict=True)


@pytest.mark.unit
def test_invalid_window_recorded_as_error() -> None:
    def cb(a: date, b: date) -> int:
        return 1

    rows = run_walk_forward_windows([(date(2020, 2, 1), date(2020, 1, 1))], cb)
    assert rows[0].metrics is None
    assert rows[0].error is not None
    assert "after end" in (rows[0].error or "")

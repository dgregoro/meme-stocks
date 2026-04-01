"""Unit tests for S5 cross-sectional dispersion helpers (no DB)."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.s5_cross_sectional_dispersion import dispersion_feature_by_date


@pytest.mark.unit
def test_dispersion_feature_insufficient_members_returns_none() -> None:
    close_by = {
        "A": {date(2024, 1, 2): 100.0, date(2024, 1, 3): 101.0},
        "B": {date(2024, 1, 2): 100.0, date(2024, 1, 3): 102.0},
    }
    feat = dispersion_feature_by_date(close_by, ("A", "B"), min_symbols=3)
    assert feat[date(2024, 1, 2)] is None
    assert feat[date(2024, 1, 3)] is None


@pytest.mark.unit
def test_dispersion_feature_two_symbols_computes_stdev() -> None:
    close_by = {
        "A": {date(2024, 1, 2): 100.0, date(2024, 1, 3): 101.0},
        "B": {date(2024, 1, 2): 100.0, date(2024, 1, 3): 104.0},
    }
    feat = dispersion_feature_by_date(close_by, ("A", "B"), min_symbols=2)
    assert feat[date(2024, 1, 2)] is None
    v = feat[date(2024, 1, 3)]
    assert v is not None
    assert v > 0

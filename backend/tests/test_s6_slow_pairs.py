"""Unit tests for S6 slow-pair feature helpers (pure math / alignment)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.services.s6_slow_pairs import (
    aligned_pair_log_closes,
    build_s6_z_feature_by_date,
    ols_alpha_beta,
    s6_regime_by_date,
)


@pytest.mark.unit
def test_ols_alpha_beta_perfect_line() -> None:
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [2.0, 4.0, 6.0, 8.0]
    ab = ols_alpha_beta(xs, ys)
    assert ab is not None
    alpha, beta = ab
    assert abs(alpha) < 1e-9
    assert abs(beta - 2.0) < 1e-9


@pytest.mark.unit
def test_ols_alpha_beta_degenerate_x() -> None:
    assert ols_alpha_beta([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None


@pytest.mark.unit
def test_aligned_pair_log_closes_filters_positive() -> None:
    d1, d2, d3 = date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)
    a = {d1: 100.0, d2: 0.0, d3: 101.0}
    b = {d1: 50.0, d2: 50.0, d3: 50.5}
    dates, la, lb = aligned_pair_log_closes(a, b)
    assert dates == [d1, d3]
    assert len(la) == 2 and la[0] > 4.6


@pytest.mark.unit
def test_build_s6_z_feature_produces_late_dates() -> None:
    """With tiny windows, z should exist once spread residuals vary (noise breaks perfect collinearity)."""
    days = [date(2024, 1, 2) + timedelta(days=i) for i in range(40)]
    log_a = [4.605 + 0.001 * i + 0.002 * ((-1) ** i) for i in range(40)]
    log_b = [3.912 + 0.0008 * i + 0.001 * (i % 3) for i in range(40)]
    zmap = build_s6_z_feature_by_date(days, log_a, log_b, beta_window=5, z_window=5)
    nonempty = [d for d, z in zmap.items() if z is not None]
    assert len(nonempty) >= 5
    assert all(isinstance(zmap[d], float) for d in nonempty)


@pytest.mark.unit
def test_s6_regime_by_date_bucket_strings() -> None:
    d0 = date(2024, 1, 2)
    zfeat = {d0 + timedelta(days=i): float(i % 7) for i in range(30)}
    reg = s6_regime_by_date(zfeat, min_history=5, n_buckets=4)
    assert any(reg[d] is not None for d in zfeat)

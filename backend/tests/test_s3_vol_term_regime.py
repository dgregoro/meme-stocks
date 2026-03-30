"""Unit tests for S3 vol term-structure feature and expanding quantile regimes."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.services.s3_vol_term_regime import (
    compute_s3_feature,
    prior_expanding_quantile_regimes,
    s3_bucket_keys,
)


@pytest.mark.unit
def test_compute_s3_feature_spread() -> None:
    assert compute_s3_feature(20.0, 22.0, use_ratio=False, denom_floor=0.01) == pytest.approx(-2.0)


@pytest.mark.unit
def test_compute_s3_feature_ratio() -> None:
    r = compute_s3_feature(20.0, 25.0, use_ratio=True, denom_floor=0.01)
    assert r == pytest.approx(0.8)


@pytest.mark.unit
def test_compute_s3_feature_ratio_respects_floor() -> None:
    r = compute_s3_feature(20.0, 0.001, use_ratio=True, denom_floor=1.0)
    assert r == pytest.approx(20.0)


@pytest.mark.unit
def test_compute_s3_feature_invalid_returns_none() -> None:
    assert compute_s3_feature(-1.0, 20.0, use_ratio=False, denom_floor=0.01) is None
    assert compute_s3_feature(20.0, 0.0, use_ratio=False, denom_floor=0.01) is None


@pytest.mark.unit
def test_prior_expanding_labels_after_min_history() -> None:
    base = date(2024, 1, 2)
    fb = {base + timedelta(days=i): float(i) for i in range(30)}
    reg = prior_expanding_quantile_regimes(fb, min_history=10, n_buckets=4)
    assert reg[base] is None
    # day index 9 -> 10 values 0..9
    d9 = base + timedelta(days=9)
    assert reg[d9] in s3_bucket_keys(4)


@pytest.mark.unit
def test_s3_bucket_keys_length() -> None:
    assert s3_bucket_keys(4) == ("q0", "q1", "q2", "q3")

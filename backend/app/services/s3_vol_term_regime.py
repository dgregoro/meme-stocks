"""S3 regime labels: prior-only expanding quantile buckets on a vol term-structure feature."""

from __future__ import annotations

import bisect
import datetime as dt
import statistics
from typing import Mapping


def compute_s3_feature(
    vix_close: float,
    vix3m_close: float,
    *,
    use_ratio: bool,
    denom_floor: float,
) -> float | None:
    """Return spread (VIX − VIX3M) or ratio (VIX / VIX3M) with denominator guard."""
    if vix_close <= 0 or vix3m_close <= 0:
        return None
    if use_ratio:
        den = max(float(vix3m_close), float(denom_floor))
        if den <= 0:
            return None
        return float(vix_close) / den
    return float(vix_close) - float(vix3m_close)


def prior_expanding_quantile_regimes(
    feature_by_date: Mapping[dt.date, float | None],
    *,
    min_history: int,
    n_buckets: int,
) -> dict[dt.date, str | None]:
    """For each date (sorted), assign q0..q{n-1} using quantiles of history ≤ date.

    Dates with no feature are labeled None until/unless a value exists.
    Requires at least ``min_history`` non-null feature values in the expanding window.
    """
    if n_buckets < 2:
        raise ValueError("n_buckets must be >= 2")
    ordered = sorted(feature_by_date.keys())
    out: dict[dt.date, str | None] = dict.fromkeys(ordered)

    for d in ordered:
        cur = feature_by_date.get(d)
        vals = []
        for u in ordered:
            if u > d:
                break
            fv = feature_by_date.get(u)
            if fv is not None:
                vals.append(float(fv))
        if cur is None or len(vals) < min_history:
            out[d] = None
            continue
        try:
            cuts = statistics.quantiles(vals, n=n_buckets, method="inclusive")
        except statistics.StatisticsError:
            out[d] = None
            continue
        bidx = bisect.bisect_right(cuts, float(cur))
        out[d] = f"q{bidx}"

    return out


def s3_bucket_keys(n_buckets: int) -> tuple[str, ...]:
    return tuple(f"q{i}" for i in range(n_buckets))

"""S5: cross-sectional dispersion of simple daily returns across an explicit symbol panel.

Dispersion on date *d* uses consecutive dates in the **sorted union** of panel trading dates:
*previous union date → d*. For each symbol with valid closes on both dates,
* r = c_d / c_prev - 1. Population stdev of *r* is *D_d* when at least ``min_symbols`` returns exist.

Regime labels reuse :func:`prior_expanding_quantile_regimes` (same causal expanding history as S3).
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy.orm import Session

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.services.s3_vol_term_regime import prior_expanding_quantile_regimes


def load_closes_by_symbol(
    db: Session,
    universe: Sequence[str],
    load_start: date,
    load_end: date,
) -> dict[str, dict[date, float]]:
    """Map symbol → { trade_date: close } for dates in ``[load_start, load_end]`` with positive close."""
    repo = PriceDataRepository(db)
    out: dict[str, dict[date, float]] = {}
    for sym in universe:
        su = sym.strip().upper()
        rows = list(repo.list_for_stock(su))
        m: dict[date, float] = {}
        for r in rows:
            if load_start <= r.date <= load_end and r.close is not None and float(r.close) > 0:
                m[r.date] = float(r.close)
        out[su] = m
    return out


def dispersion_feature_by_date(
    close_by_symbol: Mapping[str, Mapping[date, float]],
    universe: Sequence[str],
    *,
    min_symbols: int,
) -> dict[date, float | None]:
    """Cross-sectional stdev of simple returns between consecutive union-calendar dates."""
    syms = [s.strip().upper() for s in universe]
    all_dates: set[date] = set()
    for s in syms:
        all_dates.update(close_by_symbol.get(s, {}).keys())
    ordered = sorted(all_dates)
    feature: dict[date, float | None] = {d: None for d in ordered}

    for i in range(1, len(ordered)):
        d_prev, d = ordered[i - 1], ordered[i]
        rets: list[float] = []
        for s in syms:
            c0 = close_by_symbol.get(s, {}).get(d_prev)
            c1 = close_by_symbol.get(s, {}).get(d)
            if c0 is not None and c1 is not None and c0 > 0:
                rets.append(c1 / c0 - 1.0)
        if len(rets) >= min_symbols:
            feature[d] = statistics.pstdev(rets)
        else:
            feature[d] = None

    return feature


def s5_regime_by_date(
    feature_by_date: Mapping[date, float | None],
    *,
    min_history: int,
    n_buckets: int,
) -> dict[date, str | None]:
    """Expanding quantile regimes (q0..q{n-1}) on the dispersion series."""
    return prior_expanding_quantile_regimes(
        feature_by_date,
        min_history=min_history,
        n_buckets=n_buckets,
    )


def count_nonnull_features(
    feature_by_date: Mapping[date, float | None],
    *,
    since: date | None,
    until: date | None,
) -> int:
    """Count dates in optional ``[since, until]`` with a non-null feature value."""
    n = 0
    for d, v in feature_by_date.items():
        if v is None:
            continue
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        n += 1
    return n

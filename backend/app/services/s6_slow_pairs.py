"""S6: slow pair / relative value — causal log-price hedge residual and rolling z-score.

Beta and spread moments use only **prior** overlapping observations (see specs/024 research.md).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from typing import cast
from datetime import date

from sqlalchemy.orm import Session

from backend.app.services.s5_cross_sectional_dispersion import load_closes_by_symbol
from backend.app.services.s3_vol_term_regime import prior_expanding_quantile_regimes


def ols_alpha_beta(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float] | None:
    """Fit y ~ alpha + beta * x; return (alpha, beta) or None."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den <= 1e-18:
        return None
    beta = num / den
    alpha = my - beta * mx
    return alpha, beta


def aligned_pair_log_closes(
    close_a_by_date: Mapping[date, float],
    close_b_by_date: Mapping[date, float],
) -> tuple[list[date], list[float], list[float]]:
    """Sorted intersection of dates with positive closes; natural logs."""
    common = sorted(set(close_a_by_date) & set(close_b_by_date))
    dates: list[date] = []
    log_a: list[float] = []
    log_b: list[float] = []
    for d in common:
        ca = float(close_a_by_date[d])
        cb = float(close_b_by_date[d])
        if ca > 0 and cb > 0:
            dates.append(d)
            log_a.append(math.log(ca))
            log_b.append(math.log(cb))
    return dates, log_a, log_b


def build_s6_z_feature_by_date(
    dates: Sequence[date],
    log_a: Sequence[float],
    log_b: Sequence[float],
    *,
    beta_window: int,
    z_window: int,
) -> dict[date, float | None]:
    """Per day: OLS on prior ``beta_window`` points, spread residual, z vs prior ``z_window`` spreads."""
    n = len(dates)
    w = max(2, int(beta_window))
    z_win = max(2, int(z_window))
    out: dict[date, float | None] = {d: None for d in dates}
    if n == 0:
        return out

    spreads: list[float | None] = [None] * n
    for i in range(n):
        if i < w:
            continue
        xs = list(log_b[i - w : i])
        ys = list(log_a[i - w : i])
        est = ols_alpha_beta(xs, ys)
        if est is None:
            continue
        alpha, beta = est
        spreads[i] = float(log_a[i]) - alpha - beta * float(log_b[i])

    for i in range(n):
        if spreads[i] is None:
            continue
        if i < w + z_win:
            continue
        hist = [spreads[j] for j in range(i - z_win, i)]
        if any(h is None for h in hist):
            continue
        hf = [float(cast(float, h)) for h in hist]
        mu = statistics.fmean(hf)
        sd = statistics.pstdev(hf)
        if sd < 1e-12:
            continue
        sp_i = spreads[i]
        if sp_i is None:
            continue
        out[dates[i]] = (float(sp_i) - mu) / sd

    return out


def s6_regime_by_date(
    z_feature_by_date: Mapping[date, float | None],
    *,
    min_history: int,
    n_buckets: int,
) -> dict[date, str | None]:
    """Expanding quantile regimes on the causal z-score series."""
    return prior_expanding_quantile_regimes(
        z_feature_by_date,
        min_history=min_history,
        n_buckets=n_buckets,
    )


def load_pair_close_maps(
    db: Session,
    leg_a: str,
    leg_b: str,
    load_start: date,
    load_end: date,
) -> tuple[dict[date, float], dict[date, float]]:
    """Positive closes only, from ``load_start`` through ``load_end`` inclusive."""
    pair = (leg_a.strip().upper(), leg_b.strip().upper())
    by_sym = load_closes_by_symbol(db, pair, load_start=load_start, load_end=load_end)
    return by_sym[pair[0]], by_sym[pair[1]]

"""Daily-frequency strategy research (STRATEGY_EXPLORATION S1–S6).

Pure feature construction and forward-return summaries: S4 calendar flags; S5 panel dispersion; S6 slow pairs.
See docs/STRATEGY_TESTING_PLAN.md and docs/STRATEGY_EXPLORATION.md.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal, Sequence, cast

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.vol_term_structure_repo import VolTermStructureRepository
from backend.app.services.research_execution.window_splits import (
    split_calendar_range,
    split_sorted_trading_days,
)
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.services.leader_follower_evaluation_service import compute_forward_return
from backend.app.services.s4_calendar_flags import (
    is_calendar_month_end,
    is_opex_week,
    is_quarter_end_calendar,
    s4_bucket_label,
)
from backend.app.services.s3_vol_term_regime import (
    compute_s3_feature,
    prior_expanding_quantile_regimes,
    s3_bucket_keys,
)
from backend.app.services.s5_cross_sectional_dispersion import (
    count_nonnull_features,
    dispersion_feature_by_date,
    load_closes_by_symbol,
    s5_regime_by_date,
)
from backend.app.services.s6_slow_pairs import (
    aligned_pair_log_closes,
    build_s6_z_feature_by_date,
    load_pair_close_maps,
    s6_regime_by_date,
)

logger = logging.getLogger(__name__)

SplitMode = Literal["calendar", "trading"]
StrategyMeritId = Literal["s1", "s2", "s3", "s4", "s5", "s6"]


@dataclass(frozen=True)
class DailyBar:
    """One daily OHLCV observation (sorted ascending by date in a series)."""

    d: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def _parse_horizons_setting(raw: str | None) -> tuple[int, ...]:
    if not raw or not isinstance(raw, str):
        return (1, 5, 10)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return (1, 5, 10)
    try:
        return tuple(sorted(set(int(h) for h in parts if int(h) > 0)))
    except (ValueError, TypeError):
        return (1, 5, 10)


def bars_from_price_rows(rows: Sequence[PriceData]) -> list[DailyBar]:
    """Filter to valid OHLCV rows and sort by date."""
    out: list[DailyBar] = []
    for r in rows:
        if r.close and r.close > 0 and r.open and r.open > 0 and r.volume is not None and r.volume >= 0:
            out.append(
                DailyBar(
                    d=r.date,
                    open=float(r.open),
                    high=float(r.high),
                    low=float(r.low),
                    close=float(r.close),
                    volume=int(r.volume),
                )
            )
    out.sort(key=lambda b: b.d)
    return out


def realized_vol_series(closes: Sequence[float], window: int) -> list[float | None]:
    """Sample stdev of log returns over trailing ``window`` trading days (inclusive end).

    Index i uses returns ending at i; needs window returns -> window+1 closes.
    """
    n = len(closes)
    if window < 2:
        raise ValueError("window must be >= 2")
    out: list[float | None] = [None] * n
    log_rets: list[float | None] = [None] * n
    for i in range(1, n):
        a, b = closes[i - 1], closes[i]
        if a > 0 and b > 0:
            log_rets[i] = math.log(b / a)
    for i in range(window, n):
        chunk_maybe = [log_rets[j] for j in range(i - window + 1, i + 1) if log_rets[j] is not None]
        if len(chunk_maybe) < window:
            continue
        chunk = cast(list[float], chunk_maybe)
        try:
            out[i] = statistics.stdev(chunk)
        except statistics.StatisticsError:
            out[i] = None
    return out


def volume_log_z_series(volumes: Sequence[int], window: int) -> list[float | None]:
    """Z-score of log(volume+1) vs trailing ``window`` days inclusive (end of day signal)."""
    n = len(volumes)
    if window < 2:
        raise ValueError("window must be >= 2")
    logs = [math.log(max(0, v) + 1.0) for v in volumes]
    out: list[float | None] = [None] * n
    for i in range(window - 1, n):
        chunk = logs[i - window + 1 : i + 1]
        try:
            m = statistics.mean(chunk)
            sd = statistics.stdev(chunk)
        except statistics.StatisticsError:
            continue
        if sd == 0:
            continue
        out[i] = (logs[i] - m) / sd
    return out


S1Regime = Literal["hv_lv", "lv_hv", "neutral"]


def classify_s1_regime(
    rv: float,
    vz: float,
    past_rv: Sequence[float],
    past_vz: Sequence[float],
) -> S1Regime | None:
    """High realized vol + low volume z vs low rv + high vz; else neutral. Medians over prior samples only."""
    if len(past_rv) < 2 or len(past_vz) < 2:
        return None
    med_rv = statistics.median(past_rv)
    med_vz = statistics.median(past_vz)
    hv_lv = rv >= med_rv and vz <= med_vz
    lv_hv = rv <= med_rv and vz >= med_vz
    if hv_lv and not lv_hv:
        return "hv_lv"
    if lv_hv and not hv_lv:
        return "lv_hv"
    if hv_lv and lv_hv:
        return "neutral"
    return "neutral"


def simple_sma(closes: Sequence[float], window: int, end_index_inclusive: int) -> float | None:
    """SMA over closes[end - window + 1 : end + 1]. end_index_inclusive is index in closes."""
    if window < 1 or end_index_inclusive < window - 1:
        return None
    start = end_index_inclusive - window + 1
    chunk = closes[start : end_index_inclusive + 1]
    if len(chunk) != window or any(c <= 0 for c in chunk):
        return None
    return sum(chunk) / window


S2Bucket = Literal[
    "gap_up_uptrend",
    "gap_up_downtrend",
    "gap_down_downtrend",
    "gap_down_uptrend",
    "flat_gap",
]


def classify_s2_bucket(gap_pct: float, uptrend: bool | None) -> S2Bucket | None:
    if uptrend is None:
        return None
    eps = 1e-6
    if abs(gap_pct) < eps:
        return "flat_gap"
    if gap_pct > 0:
        return "gap_up_uptrend" if uptrend else "gap_up_downtrend"
    return "gap_down_downtrend" if not uptrend else "gap_down_uptrend"


def metrics_from_returns(returns: list[float]) -> dict[str, Any]:
    if not returns:
        return {
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "median_return_pct": 0.0,
            "evaluable_count": 0,
        }
    n = len(returns)
    wins = sum(1 for r in returns if r > 0)
    avg = round(sum(returns) / n, 4)
    sorted_r = sorted(returns)
    mid = n // 2
    med = sorted_r[mid] if n % 2 else (sorted_r[mid - 1] + sorted_r[mid]) / 2
    return {
        "win_rate": round(wins / n, 4),
        "avg_return_pct": avg,
        "median_return_pct": round(med, 4),
        "evaluable_count": n,
    }


def _macro_vol_term_data_hint() -> str:
    return (
        "Insufficient VIX/VIX3M macro history for S3 (need s3_regime_min_history_days qualifying features). "
        "Run: python -m backend.app.cli backfill vol-term --start 2010-01-01 --end 2025-12-31"
    )


def _price_data_hint(db: Session, symbol: str, n_price_rows_raw: int, n_valid_bars: int) -> str:
    """Human-readable next step when evaluation has too little usable data."""
    stock = StockRepository(db).get(symbol)
    if stock is None:
        return (
            f"No row in `stocks` for {symbol}. Run: python -m backend.app.cli seed stocks "
            f"(SPY is in the benchmarks group), then optionally: seed stock-groups. "
            f"Then backfill daily OHLCV (see hint for symbols already in `stocks`)."
        )
    if n_price_rows_raw == 0:
        return (
            f"`stocks` has {symbol} but `price_data` is empty. Run: "
            f"python -m backend.app.cli backfill daily-prices --start 2018-01-01 --end 2025-12-31 "
            f"--symbols {symbol} "
            f"(requires ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY), "
            f"or wait for the scheduler to collect Yahoo history for tracked symbols."
        )
    if n_valid_bars == 0:
        return (
            f"{symbol} has {n_price_rows_raw} price_data row(s) but none passed validation "
            f"(need positive O/H/L/C and non-negative volume). Check data quality."
        )
    return (
        f"Need more trading days for warm-up windows (have {n_valid_bars} valid bars). "
        f"Extend the backfill date range or lower daily_strategy_* windows in config."
    )


def _price_close_dict(bars: Sequence[DailyBar]) -> dict[str, list[tuple[date, float]]]:
    if not bars:
        return {}
    sym = "_series"  # single-series key for compute_forward_return
    return {sym: [(b.d, b.close) for b in bars]}


@dataclass(frozen=True)
class S1WindowSample:
    """Labeled regime forward returns + unconditional baseline (same calendar days) for one symbol."""

    regime_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


S2_BUCKET_KEYS: tuple[str, ...] = (
    "gap_up_uptrend",
    "gap_up_downtrend",
    "gap_down_downtrend",
    "gap_down_uptrend",
    "flat_gap",
)


@dataclass(frozen=True)
class S2WindowSample:
    """Gap-ecology bucket forward returns + baseline for one symbol."""

    bucket_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


@dataclass(frozen=True)
class S3WindowSample:
    """Vol term-structure quantile regime forward returns + baseline for one symbol."""

    regime_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


S4_BUCKET_KEYS: tuple[str, ...] = tuple(f"cal_{a}{b}{c}" for a in (0, 1) for b in (0, 1) for c in (0, 1))


@dataclass(frozen=True)
class S4WindowSample:
    """Calendar-flag bucket forward returns + baseline for one symbol (S4)."""

    bucket_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


@dataclass(frozen=True)
class S5WindowSample:
    """Cross-sectional dispersion quantile regime forward returns + baseline (S5)."""

    regime_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


@dataclass(frozen=True)
class S6WindowSample:
    """Slow-pair spread z-score quantile regime forward returns on leg A + baseline (S6)."""

    regime_returns: dict[str, dict[str, list[float]]]
    baseline_returns: dict[str, list[float]]
    counts: dict[str, int]


def _load_s3_feature_by_date(
    db: Session,
    *,
    load_start: date,
    load_end: date,
) -> dict[date, float | None]:
    settings = get_settings()
    use_ratio = settings.s3_feature_mode.strip().lower() == "ratio"
    floor = float(settings.s3_ratio_denominator_floor)
    repo = VolTermStructureRepository(db)
    rows = repo.list_between(load_start, load_end)
    out: dict[date, float | None] = {}
    for r in rows:
        out[r.observation_date] = compute_s3_feature(
            r.vix_close,
            r.vix3m_close,
            use_ratio=use_ratio,
            denom_floor=floor,
        )
    return out


def _compute_s3_window_sample(
    db: Session,
    bars: list[DailyBar],
    *,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
) -> S3WindowSample | None:
    """Baseline + expanding-quantile regime buckets from VIX/VIX3M feature (DB-backed)."""
    min_needed = max(horizons) + 5
    if len(bars) < min_needed:
        return None
    settings = get_settings()
    n_bk = max(2, min(20, int(settings.s3_regime_n_buckets)))
    min_hist = max(2, int(settings.s3_regime_min_history_days))
    buf = max(1, int(settings.s3_macro_backfill_calendar_buffer_days))
    d_first, d_last = bars[0].d, bars[-1].d
    load_start = d_first - timedelta(days=buf)
    feature_by_date = _load_s3_feature_by_date(db, load_start=load_start, load_end=d_last)
    regime_by_date = prior_expanding_quantile_regimes(
        feature_by_date,
        min_history=min_hist,
        n_buckets=n_bk,
    )
    bucket_keys = s3_bucket_keys(n_bk)
    by_reg: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {k: 0 for k in bucket_keys}
    price_one = _price_close_dict(bars)
    dates = [b.d for b in bars]

    for i in range(len(bars)):
        d = dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)
        lab = regime_by_date.get(d)
        if lab is None or lab not in by_reg:
            continue
        counts[lab] = counts.get(lab, 0) + 1
        for h, fr in forwards.items():
            by_reg[lab][str(h)].append(fr)

    return S3WindowSample(regime_returns=by_reg, baseline_returns=baseline, counts=counts)


def _compute_s1_window_sample(
    bars: list[DailyBar],
    *,
    vol_w: int,
    vz_w: int,
    lookback: int,
    min_prior: int,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
) -> S1WindowSample | None:
    """Build regime-labeled and baseline forward-return samples for dates in [since, until]."""
    min_needed = max(vol_w, vz_w) + min_prior + max(horizons) + 5
    if len(bars) < min_needed:
        return None

    closes = [b.close for b in bars]
    vols = [b.volume for b in bars]
    dates = [b.d for b in bars]
    rv = realized_vol_series(closes, vol_w)
    vz = volume_log_z_series(vols, vz_w)
    warm = max(vol_w, vz_w - 1) + min_prior + 1

    by_regime: dict[str, dict[str, list[float]]] = {
        "hv_lv": {str(h): [] for h in horizons},
        "lv_hv": {str(h): [] for h in horizons},
        "neutral": {str(h): [] for h in horizons},
    }
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {"hv_lv": 0, "lv_hv": 0, "neutral": 0}
    price_one = _price_close_dict(bars)

    for i in range(warm, len(bars)):
        d = dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)

        rvi, vzi = rv[i], vz[i]
        if rvi is None or vzi is None:
            continue
        past_rv: list[float] = []
        past_vz: list[float] = []
        for j in range(max(0, i - lookback), i):
            rv_j = rv[j]
            if rv_j is not None:
                past_rv.append(rv_j)
            vz_j = vz[j]
            if vz_j is not None:
                past_vz.append(vz_j)
        if len(past_rv) < min_prior or len(past_vz) < min_prior:
            continue
        regime_label = classify_s1_regime(float(rvi), float(vzi), past_rv, past_vz)
        if regime_label is None:
            continue
        counts[regime_label] = counts.get(regime_label, 0) + 1
        for h, fr in forwards.items():
            by_regime[regime_label][str(h)].append(fr)

    return S1WindowSample(regime_returns=by_regime, baseline_returns=baseline, counts=counts)


def _compute_s2_window_sample(
    bars: list[DailyBar],
    *,
    ma_w: int,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
) -> S2WindowSample | None:
    min_needed = ma_w + max(horizons) + 5
    if len(bars) < min_needed:
        return None

    closes = [b.close for b in bars]
    opens = [b.open for b in bars]
    dates = [b.d for b in bars]
    by_bucket: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in S2_BUCKET_KEYS}
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {k: 0 for k in S2_BUCKET_KEYS}
    price_one = _price_close_dict(bars)

    for i in range(1, len(bars)):
        d = dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        if i < ma_w:
            continue
        prev_c = closes[i - 1]
        if prev_c <= 0:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)

        gap_pct = (opens[i] / prev_c - 1.0) * 100.0
        sma_prev = simple_sma(closes, ma_w, i - 1)
        if sma_prev is None:
            continue
        uptrend = closes[i - 1] > sma_prev
        bucket = classify_s2_bucket(gap_pct, uptrend)
        if bucket is None:
            continue
        counts[bucket] = counts.get(bucket, 0) + 1
        for h, fr in forwards.items():
            by_bucket[bucket][str(h)].append(fr)

    return S2WindowSample(bucket_returns=by_bucket, baseline_returns=baseline, counts=counts)


def _compute_s4_window_sample(
    bars: list[DailyBar],
    *,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
    settings: Any | None = None,
) -> S4WindowSample | None:
    """Calendar-flag buckets (OpEx week, calendar month-end, calendar quarter-end union) vs baseline."""
    st = settings if settings is not None else get_settings()
    min_needed = max(horizons) + 5
    if len(bars) < min_needed:
        return None

    inc_o = bool(getattr(st, "s4_include_opex_week", True))
    inc_m = bool(getattr(st, "s4_include_calendar_month_end", True))
    inc_q = bool(getattr(st, "s4_include_quarter_end_calendar", True))
    if not (inc_o or inc_m or inc_q):
        return None

    by_bucket: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in S4_BUCKET_KEYS}
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {k: 0 for k in S4_BUCKET_KEYS}
    price_one = _price_close_dict(bars)
    dates = [b.d for b in bars]

    for i in range(len(bars)):
        d = dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)

        opex = is_opex_week(d) if inc_o else False
        m_end = is_calendar_month_end(d) if inc_m else False
        q_end = is_quarter_end_calendar(d) if inc_q else False
        if not (opex or m_end or q_end):
            continue
        label = s4_bucket_label(
            opex_week=opex,
            month_end=m_end,
            quarter_end=q_end,
            include_opex=inc_o,
            include_month_end=inc_m,
            include_quarter_end=inc_q,
        )
        counts[label] = counts.get(label, 0) + 1
        for h, fr in forwards.items():
            by_bucket[label][str(h)].append(fr)

    return S4WindowSample(bucket_returns=by_bucket, baseline_returns=baseline, counts=counts)


def _compute_s5_window_sample(
    db: Session,
    bars: list[DailyBar],
    panel_universe: list[str],
    *,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
) -> S5WindowSample | None:
    """Expanding quantile regimes on cross-sectional return dispersion; labels equity days for one symbol."""
    min_needed = max(horizons) + 5
    if len(bars) < min_needed:
        return None

    settings = get_settings()
    n_bk = max(2, min(20, int(settings.s5_regime_n_buckets)))
    min_hist = max(2, int(settings.s5_regime_min_history_days))
    min_xs = max(2, int(settings.s5_min_symbols_cross_section))
    buf = max(1, int(settings.s5_load_buffer_calendar_days))
    uni = list(dict.fromkeys(s.strip().upper() for s in panel_universe))
    if len(uni) < min_xs:
        return None

    d_first, d_last = bars[0].d, bars[-1].d
    load_start = d_first - timedelta(days=buf)
    close_by = load_closes_by_symbol(db, uni, load_start=load_start, load_end=d_last)
    feature_by_date = dispersion_feature_by_date(close_by, uni, min_symbols=min_xs)
    regime_by_date = s5_regime_by_date(feature_by_date, min_history=min_hist, n_buckets=n_bk)
    bucket_keys = s3_bucket_keys(n_bk)
    by_reg: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {k: 0 for k in bucket_keys}
    price_one = _price_close_dict(bars)
    dates = [b.d for b in bars]

    for i in range(len(bars)):
        d = dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)
        lab = regime_by_date.get(d)
        if lab is None or lab not in by_reg:
            continue
        counts[lab] = counts.get(lab, 0) + 1
        for h, fr in forwards.items():
            by_reg[lab][str(h)].append(fr)

    return S5WindowSample(regime_returns=by_reg, baseline_returns=baseline, counts=counts)


def _compute_s6_window_sample(
    db: Session,
    bars_a: list[DailyBar],
    leg_a: str,
    leg_b: str,
    *,
    horizons: tuple[int, ...],
    since: date | None,
    until: date | None,
) -> S6WindowSample | None:
    """Expanding quantile regimes on causal spread z vs forward returns on leg A."""
    settings = get_settings()
    w = max(2, int(settings.s6_beta_window_days))
    z_w = max(2, int(settings.s6_zscore_window_days))
    n_bk = max(2, min(20, int(settings.s6_regime_n_buckets)))
    min_hist = max(2, int(settings.s6_regime_min_history_days))
    buf = max(1, int(settings.s6_load_buffer_calendar_days))
    leg_au, leg_bu = leg_a.strip().upper(), leg_b.strip().upper()
    if leg_au == leg_bu:
        return None
    min_align = w + z_w + max(horizons) + 5 + min_hist
    if len(bars_a) < min_align:
        return None

    d_first, d_last = bars_a[0].d, bars_a[-1].d
    load_start = d_first - timedelta(days=buf)
    ca, cb = load_pair_close_maps(db, leg_au, leg_bu, load_start=load_start, load_end=d_last)
    dates, log_a, log_b = aligned_pair_log_closes(ca, cb)
    if len(dates) < min_align:
        return None

    z_by_date = build_s6_z_feature_by_date(dates, log_a, log_b, beta_window=w, z_window=z_w)
    regime_by_date = s6_regime_by_date(z_by_date, min_history=min_hist, n_buckets=n_bk)
    bucket_keys = s3_bucket_keys(n_bk)
    by_reg: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    baseline: dict[str, list[float]] = {str(h): [] for h in horizons}
    counts: dict[str, int] = {k: 0 for k in bucket_keys}
    price_one = _price_close_dict(bars_a)
    bar_dates = [b.d for b in bars_a]

    for i in range(len(bars_a)):
        d = bar_dates[i]
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        forwards: dict[int, float] = {}
        for h in horizons:
            fr = compute_forward_return("_series", d, h, price_one)
            if fr is not None:
                forwards[h] = fr
        for h, fr in forwards.items():
            baseline[str(h)].append(fr)
        lab = regime_by_date.get(d)
        if lab is None or lab not in by_reg:
            continue
        counts[lab] = counts.get(lab, 0) + 1
        for h, fr in forwards.items():
            by_reg[lab][str(h)].append(fr)

    return S6WindowSample(regime_returns=by_reg, baseline_returns=baseline, counts=counts)


@dataclass(frozen=True)
class DailyStrategySymbolDataAssessment:
    """Result of a read-only data sufficiency check for S1–S6 daily strategy eval."""

    symbol: str
    status: Literal["ready", "missing_stock", "insufficient_history"]
    message: str | None
    min_bars_required: int
    valid_bar_count: int
    raw_price_row_count: int


def daily_strategy_min_valid_bars(strategy: StrategyMeritId) -> int:
    """Minimum valid daily bars required (same contract as _compute_s1/_compute_s2/_compute_s3/_compute_s4)."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    if strategy == "s1":
        vol_w = max(2, settings.daily_strategy_realized_vol_window)
        vz_w = max(2, settings.daily_strategy_volume_z_window)
        min_prior = max(10, settings.daily_strategy_regime_min_prior_days)
        return max(vol_w, vz_w) + min_prior + max(horizons) + 5
    if strategy == "s3":
        return max(horizons) + 5
    if strategy == "s4":
        return max(horizons) + 5
    if strategy == "s5":
        min_hist = max(2, int(settings.s5_regime_min_history_days))
        return max(horizons) + 5 + min_hist
    if strategy == "s6":
        w = max(2, int(settings.s6_beta_window_days))
        z_w = max(2, int(settings.s6_zscore_window_days))
        min_hist = max(2, int(settings.s6_regime_min_history_days))
        return w + z_w + max(horizons) + 5 + min_hist
    ma_w = max(2, settings.daily_strategy_gap_ma_window)
    return ma_w + max(horizons) + 5


def assess_daily_strategy_symbol_data(
    db: Session,
    symbol: str,
    strategy: StrategyMeritId,
    eval_start: date | None,
    eval_end: date | None,
    *,
    panel_universe: Sequence[str] | None = None,
    pair_leg_b: str | None = None,
) -> DailyStrategySymbolDataAssessment:
    """Check whether ``price_data`` and ``stocks`` support evaluation for one symbol.

    Uses the same feature windows as merit / single-symbol eval (S1–S6 compute paths).
    For ``strategy=="s5"``, pass ``panel_universe`` (full symbol list); the subject must be included.
    For ``strategy=="s6"``, pass ``pair_leg_b`` (leg B); ``symbol`` is leg A.
    """
    symu = symbol.strip().upper()
    stock_repo = StockRepository(db)
    if stock_repo.get(symu) is None:
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="missing_stock",
            message=_price_data_hint(db, symu, 0, 0),
            min_bars_required=daily_strategy_min_valid_bars(strategy),
            valid_bar_count=0,
            raw_price_row_count=0,
        )

    settings = get_settings()
    repo = PriceDataRepository(db)
    rows = repo.list_for_stock(symu)
    bars = bars_from_price_rows(rows)
    min_need = daily_strategy_min_valid_bars(strategy)

    if strategy == "s1":
        vol_w = max(2, settings.daily_strategy_realized_vol_window)
        vz_w = max(2, settings.daily_strategy_volume_z_window)
        lookback = max(20, settings.daily_strategy_regime_lookback_days)
        min_prior = max(10, settings.daily_strategy_regime_min_prior_days)
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        if len(bars) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        s1_sample = _compute_s1_window_sample(
            bars,
            vol_w=vol_w,
            vz_w=vz_w,
            lookback=lookback,
            min_prior=min_prior,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if s1_sample is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="ready",
            message=None,
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )

    if strategy == "s3":
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        min_hist = max(2, int(settings.s3_regime_min_history_days))
        buf = max(1, int(settings.s3_macro_backfill_calendar_buffer_days))
        if len(bars) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        d_anchor = eval_start if eval_start is not None else bars[0].d
        load_end = eval_end if eval_end is not None else bars[-1].d
        load_start = d_anchor - timedelta(days=buf)
        fb = _load_s3_feature_by_date(db, load_start=load_start, load_end=load_end)
        nq = sum(1 for v in fb.values() if v is not None)
        if nq < min_hist:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_macro_vol_term_data_hint(),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        s3_sample = _compute_s3_window_sample(
            db,
            bars,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if s3_sample is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="ready",
            message=None,
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )

    if strategy == "s5":
        min_xs = max(2, int(settings.s5_min_symbols_cross_section))
        min_hist = max(2, int(settings.s5_regime_min_history_days))
        buf = max(1, int(settings.s5_load_buffer_calendar_days))
        panel = list(dict.fromkeys(s.strip().upper() for s in (panel_universe or [symu])))
        if len(bars) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        if len(panel) < min_xs:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=f"S5: panel size {len(panel)} < s5_min_symbols_cross_section ({min_xs})",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        if symu not in panel:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message="S5: subject symbol must be included in panel_universe",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        for p in panel:
            if stock_repo.get(p) is None:
                return DailyStrategySymbolDataAssessment(
                    symbol=symu,
                    status="insufficient_history",
                    message=f"S5: panel symbol {p!r} missing from stocks table",
                    min_bars_required=min_need,
                    valid_bar_count=len(bars),
                    raw_price_row_count=len(rows),
                )
        for p in panel:
            rows_p = repo.list_for_stock(p)
            bars_p = bars_from_price_rows(rows_p)
            if len(bars_p) < min_need:
                return DailyStrategySymbolDataAssessment(
                    symbol=symu,
                    status="insufficient_history",
                    message=f"S5 panel member {p}: {_price_data_hint(db, p, len(rows_p), len(bars_p))}",
                    min_bars_required=min_need,
                    valid_bar_count=len(bars),
                    raw_price_row_count=len(rows),
                )
        d_first, d_last = bars[0].d, bars[-1].d
        load_start = d_first - timedelta(days=buf)
        close_by = load_closes_by_symbol(db, panel, load_start=load_start, load_end=d_last)
        feat = dispersion_feature_by_date(close_by, panel, min_symbols=min_xs)
        n_qual = count_nonnull_features(feat, since=eval_start, until=eval_end)
        if n_qual < min_hist:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=(
                    f"S5: insufficient non-null dispersion history in panel "
                    f"({n_qual} days with feature <= eval_end, need {min_hist})"
                ),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        s5_sample = _compute_s5_window_sample(
            db,
            bars,
            panel,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if s5_sample is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="ready",
            message=None,
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )

    if strategy == "s6":
        if not pair_leg_b or not str(pair_leg_b).strip():
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message="S6: pair_leg_b (leg B ticker) is required",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        leg_b = str(pair_leg_b).strip().upper()
        if leg_b == symu:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message="S6: leg A and leg B must be different symbols",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        if stock_repo.get(leg_b) is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=f"S6: leg B {leg_b!r} missing from stocks table",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        w = max(2, int(settings.s6_beta_window_days))
        z_w = max(2, int(settings.s6_zscore_window_days))
        min_hist = max(2, int(settings.s6_regime_min_history_days))
        buf = max(1, int(settings.s6_load_buffer_calendar_days))
        rows_b = repo.list_for_stock(leg_b)
        bars_b = bars_from_price_rows(rows_b)
        if len(bars) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        if len(bars_b) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=f"S6 leg B {leg_b}: {_price_data_hint(db, leg_b, len(rows_b), len(bars_b))}",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        d_first, d_last = bars[0].d, bars[-1].d
        load_start = d_first - timedelta(days=buf)
        ca, cb = load_pair_close_maps(db, symu, leg_b, load_start=load_start, load_end=d_last)
        adates, log_a, log_b = aligned_pair_log_closes(ca, cb)
        if len(adates) < w + z_w + 5:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=(
                    f"S6: insufficient overlapping calendar days between {symu} and {leg_b} "
                    f"({len(adates)} aligned days)"
                ),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        z_feat = build_s6_z_feature_by_date(
            adates,
            log_a,
            log_b,
            beta_window=w,
            z_window=z_w,
        )
        n_qual = count_nonnull_features(z_feat, since=eval_start, until=eval_end)
        if n_qual < min_hist:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=(f"S6: insufficient non-null spread z-score days in window " f"({n_qual} vs need {min_hist})"),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        s6_sample = _compute_s6_window_sample(
            db,
            bars,
            symu,
            leg_b,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if s6_sample is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="ready",
            message=None,
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )

    if strategy == "s4":
        inc_o = bool(getattr(settings, "s4_include_opex_week", True))
        inc_m = bool(getattr(settings, "s4_include_calendar_month_end", True))
        inc_q = bool(getattr(settings, "s4_include_quarter_end_calendar", True))
        if not (inc_o or inc_m or inc_q):
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message="S4: all calendar dimensions disabled (s4_include_* config)",
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        if len(bars) < min_need:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        s4_sample = _compute_s4_window_sample(
            bars,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
            settings=settings,
        )
        if s4_sample is None:
            return DailyStrategySymbolDataAssessment(
                symbol=symu,
                status="insufficient_history",
                message=_price_data_hint(db, symu, len(rows), len(bars)),
                min_bars_required=min_need,
                valid_bar_count=len(bars),
                raw_price_row_count=len(rows),
            )
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="ready",
            message=None,
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )

    ma_w = max(2, settings.daily_strategy_gap_ma_window)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    if len(bars) < min_need:
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="insufficient_history",
            message=_price_data_hint(db, symu, len(rows), len(bars)),
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )
    s2_sample = _compute_s2_window_sample(
        bars,
        ma_w=ma_w,
        horizons=horizons,
        since=eval_start,
        until=eval_end,
    )
    if s2_sample is None:
        return DailyStrategySymbolDataAssessment(
            symbol=symu,
            status="insufficient_history",
            message=_price_data_hint(db, symu, len(rows), len(bars)),
            min_bars_required=min_need,
            valid_bar_count=len(bars),
            raw_price_row_count=len(rows),
        )
    return DailyStrategySymbolDataAssessment(
        symbol=symu,
        status="ready",
        message=None,
        min_bars_required=min_need,
        valid_bar_count=len(bars),
        raw_price_row_count=len(rows),
    )


def _top5_concentration(counts_by_symbol: dict[str, int]) -> float:
    total = sum(counts_by_symbol.values())
    if total == 0:
        return 0.0
    top5 = sum(sorted(counts_by_symbol.values(), reverse=True)[:5])
    return round(top5 / total, 4)


def _load_union_trading_days(
    db: Session,
    symbols: Sequence[str],
    start: date,
    end: date,
) -> list[date]:
    """Sorted unique dates in ``[start, end]`` present in ``price_data`` for any of ``symbols``."""
    repo = PriceDataRepository(db)
    days: set[date] = set()
    for sym in symbols:
        symu = sym.strip().upper()
        for row in repo.list_for_stock(symu):
            if start <= row.date <= end:
                days.add(row.date)
    return sorted(days)


def _merit_rolling_windows(
    db: Session,
    eval_start: date,
    eval_end: date,
    n_splits: int,
    split_mode: SplitMode,
    trading_calendar_symbols: Sequence[str],
) -> tuple[list[tuple[date, date]], str]:
    """Return (windows, mode_used). Falls back to calendar if trading union is empty."""
    n_splits = max(1, int(n_splits))
    if n_splits <= 1:
        return ([(eval_start, eval_end)], split_mode)
    if split_mode == "calendar":
        return (split_calendar_range(eval_start, eval_end, n_splits), "calendar")
    days = _load_union_trading_days(db, trading_calendar_symbols, eval_start, eval_end)
    if not days:
        return (
            split_calendar_range(eval_start, eval_end, n_splits),
            "calendar(fallback_no_trading_days_in_union)",
        )
    return (split_sorted_trading_days(days, n_splits), "trading")


def _sign_stable(values: list[float]) -> bool:
    """True if all nonzero values share the same sign (zeros ignored for sign mix check)."""
    if len(values) < 2:
        return True
    signs: set[int] = set()
    for v in values:
        if v > 1e-9:
            signs.add(1)
        elif v < -1e-9:
            signs.add(-1)
    return len(signs) <= 1


def _rollup_s1_merit_rolling(
    split_payloads: list[dict[str, Any]],
    *,
    min_events_per_regime: int,
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    """Cross-split excess stability + combined gate (see run_s1_merit_rolling_report)."""
    regimes = ("hv_lv", "lv_hv", "neutral")
    all_splits_pass = all(p["report"].get("checklist", {}).get("pass") is True for p in split_payloads)

    excess_sign_stable: dict[str, dict[str, bool | str]] = {r: {} for r in regimes}
    instability_detail: list[str] = []

    for reg in regimes:
        for hk in map(str, horizons):
            excesses: list[float] = []
            counts: list[int] = []
            for p in split_payloads:
                rep = p["report"]
                ex = rep.get("vs_baseline_avg_pct", {}).get(reg, {}).get(hk, {}).get("avg_excess_vs_baseline_pct")
                n = rep.get("by_regime", {}).get(reg, {}).get(hk, {}).get("evaluable_count", 0)
                if ex is not None and n >= min_events_per_regime:
                    excesses.append(float(ex))
                    counts.append(int(n))
            if len(excesses) < 2:
                excess_sign_stable[reg][hk] = "skipped_not_enough_splits_with_events"
            else:
                ok = _sign_stable(excesses)
                excess_sign_stable[reg][hk] = ok
                if not ok:
                    instability_detail.append(
                        f"{reg} {hk}d: excess vs baseline flips sign across splits "
                        f"(values={','.join(str(round(x, 4)) for x in excesses)})"
                    )

    strict_stable_required = [
        (r, hk) for r in regimes for hk in map(str, horizons) if excess_sign_stable[r].get(hk) is False
    ]
    rolling_pass = all_splits_pass and not strict_stable_required

    return {
        "all_splits_checklist_pass": all_splits_pass,
        "excess_vs_baseline_sign_stable": excess_sign_stable,
        "instability_failures": instability_detail,
        "rolling_pass": rolling_pass,
        "note": "rolling_pass requires every split checklist pass and no sign-flip in "
        "avg_excess_vs_baseline across splits (only splits with evaluable_count >= "
        "merit_min_events_per_regime are compared).",
    }


def _rollup_s2_merit_rolling(
    split_payloads: list[dict[str, Any]],
    *,
    min_events_per_bucket: int,
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    """Cross-split excess stability for S2 gap buckets (same logic as S1 regimes)."""
    all_splits_pass = all(p["report"].get("checklist", {}).get("pass") is True for p in split_payloads)

    excess_sign_stable: dict[str, dict[str, bool | str]] = {b: {} for b in S2_BUCKET_KEYS}
    instability_detail: list[str] = []

    for bkt in S2_BUCKET_KEYS:
        for hk in map(str, horizons):
            excesses: list[float] = []
            for p in split_payloads:
                rep = p["report"]
                ex = rep.get("vs_baseline_avg_pct", {}).get(bkt, {}).get(hk, {}).get("avg_excess_vs_baseline_pct")
                n = rep.get("by_bucket", {}).get(bkt, {}).get(hk, {}).get("evaluable_count", 0)
                if ex is not None and n >= min_events_per_bucket:
                    excesses.append(float(ex))
            if len(excesses) < 2:
                excess_sign_stable[bkt][hk] = "skipped_not_enough_splits_with_events"
            else:
                ok = _sign_stable(excesses)
                excess_sign_stable[bkt][hk] = ok
                if not ok:
                    instability_detail.append(
                        f"{bkt} {hk}d: excess vs baseline flips sign across splits "
                        f"(values={','.join(str(round(x, 4)) for x in excesses)})"
                    )

    strict_stable_required = [
        (b, hk) for b in S2_BUCKET_KEYS for hk in map(str, horizons) if excess_sign_stable[b].get(hk) is False
    ]
    rolling_pass = all_splits_pass and not strict_stable_required

    return {
        "all_splits_checklist_pass": all_splits_pass,
        "excess_vs_baseline_sign_stable": excess_sign_stable,
        "instability_failures": instability_detail,
        "rolling_pass": rolling_pass,
        "note": "Same interpretation as S1 rollup; buckets = gap ecology regimes.",
    }


def _rollup_s4_merit_rolling(
    split_payloads: list[dict[str, Any]],
    *,
    min_events_per_bucket: int,
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    """Cross-split excess stability for S4 calendar-flag buckets (same pattern as S2)."""
    all_splits_pass = all(p["report"].get("checklist", {}).get("pass") is True for p in split_payloads)

    excess_sign_stable: dict[str, dict[str, bool | str]] = {b: {} for b in S4_BUCKET_KEYS}
    instability_detail: list[str] = []

    for bkt in S4_BUCKET_KEYS:
        for hk in map(str, horizons):
            excesses: list[float] = []
            for p in split_payloads:
                rep = p["report"]
                ex = rep.get("vs_baseline_avg_pct", {}).get(bkt, {}).get(hk, {}).get("avg_excess_vs_baseline_pct")
                n = rep.get("by_bucket", {}).get(bkt, {}).get(hk, {}).get("evaluable_count", 0)
                if ex is not None and n >= min_events_per_bucket:
                    excesses.append(float(ex))
            if len(excesses) < 2:
                excess_sign_stable[bkt][hk] = "skipped_not_enough_splits_with_events"
            else:
                ok = _sign_stable(excesses)
                excess_sign_stable[bkt][hk] = ok
                if not ok:
                    instability_detail.append(
                        f"{bkt} {hk}d: excess vs baseline flips sign across splits "
                        f"(values={','.join(str(round(x, 4)) for x in excesses)})"
                    )

    strict_stable_required = [
        (b, hk) for b in S4_BUCKET_KEYS for hk in map(str, horizons) if excess_sign_stable[b].get(hk) is False
    ]
    rolling_pass = all_splits_pass and not strict_stable_required

    return {
        "all_splits_checklist_pass": all_splits_pass,
        "excess_vs_baseline_sign_stable": excess_sign_stable,
        "instability_failures": instability_detail,
        "rolling_pass": rolling_pass,
        "note": "Same interpretation as S2 rollup; buckets = calendar flag unions (cal_abc).",
    }


def _rollup_s3_merit_rolling(
    split_payloads: list[dict[str, Any]],
    *,
    min_events_per_bucket: int,
    horizons: tuple[int, ...],
    bucket_keys: tuple[str, ...],
) -> dict[str, Any]:
    """Cross-split excess stability for S3 quantile regimes (same pattern as S2)."""
    all_splits_pass = all(p["report"].get("checklist", {}).get("pass") is True for p in split_payloads)

    excess_sign_stable: dict[str, dict[str, bool | str]] = {b: {} for b in bucket_keys}
    instability_detail: list[str] = []

    for bkt in bucket_keys:
        for hk in map(str, horizons):
            excesses: list[float] = []
            for p in split_payloads:
                rep = p["report"]
                ex = rep.get("vs_baseline_avg_pct", {}).get(bkt, {}).get(hk, {}).get("avg_excess_vs_baseline_pct")
                n = rep.get("by_regime", {}).get(bkt, {}).get(hk, {}).get("evaluable_count", 0)
                if ex is not None and n >= min_events_per_bucket:
                    excesses.append(float(ex))
            if len(excesses) < 2:
                excess_sign_stable[bkt][hk] = "skipped_not_enough_splits_with_events"
            else:
                ok = _sign_stable(excesses)
                excess_sign_stable[bkt][hk] = ok
                if not ok:
                    instability_detail.append(
                        f"{bkt} {hk}d: excess vs baseline flips sign across splits "
                        f"(values={','.join(str(round(x, 4)) for x in excesses)})"
                    )

    strict_stable_required = [
        (b, hk) for b in bucket_keys for hk in map(str, horizons) if excess_sign_stable[b].get(hk) is False
    ]
    rolling_pass = all_splits_pass and not strict_stable_required

    return {
        "all_splits_checklist_pass": all_splits_pass,
        "excess_vs_baseline_sign_stable": excess_sign_stable,
        "instability_failures": instability_detail,
        "rolling_pass": rolling_pass,
        "note": "Same interpretation as S2 rollup; regimes = expanding VIX/VIX3M quantile buckets.",
    }


def run_s1_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run :func:`run_s1_merit_report` on sub-windows + stability rollup (calendar or trading days)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_reg = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s1_merit_report(db, symbols, ws, we)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s1_merit_rolling(
        split_payloads,
        min_events_per_regime=min_reg,
        horizons=horizons,
    )

    return {
        "kind": "s1_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def run_s1_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
) -> dict[str, Any]:
    """Pooled S1 evaluation over a fixed date window + baseline comparison + automated checklist.

    Reduces manual steps from SIGNAL_EVALUATION_CHECKLIST for a first pass gate.
    """
    settings = get_settings()
    vol_w = max(2, settings.daily_strategy_realized_vol_window)
    vz_w = max(2, settings.daily_strategy_volume_z_window)
    lookback = max(20, settings.daily_strategy_regime_lookback_days)
    min_prior = max(10, settings.daily_strategy_regime_min_prior_days)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_reg = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)

    repo = PriceDataRepository(db)
    pooled_regime: dict[str, dict[str, list[float]]] = {
        "hv_lv": {str(h): [] for h in horizons},
        "lv_hv": {str(h): [] for h in horizons},
        "neutral": {str(h): [] for h in horizons},
    }
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {"hv_lv": 0, "lv_hv": 0, "neutral": 0}
    regime_symbol_events: dict[str, dict[str, int]] = {
        "hv_lv": {},
        "lv_hv": {},
        "neutral": {},
    }
    skipped: list[dict[str, str]] = []

    for sym in symbols:
        symu = sym.strip().upper()
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s1_window_sample(
            bars,
            vol_w=vol_w,
            vz_w=vz_w,
            lookback=lookback,
            min_prior=min_prior,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for reg in pooled_regime:
            pooled_counts[reg] += sample.counts.get(reg, 0)
            for sy in sample.regime_returns[reg]:
                pooled_regime[reg][sy].extend(sample.regime_returns[reg][sy])
            n_ev = sample.counts.get(reg, 0)
            if n_ev:
                regime_symbol_events[reg][symu] = regime_symbol_events[reg].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    regime_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_regime: dict[str, float] = {}
    for reg, hmap in pooled_regime.items():
        regime_metrics[reg] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[reg] = {}
        conc_by_regime[reg] = _top5_concentration(regime_symbol_events[reg])
        for hk in hmap:
            rm = regime_metrics[reg][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = rm.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[reg][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    for reg in ("hv_lv", "lv_hv", "neutral"):
        for hk in map(str, horizons):
            rm = regime_metrics[reg][hk]
            n = rm.get("evaluable_count", 0)
            if n < min_reg:
                checklist_failures.append(f"{reg} horizon {hk}: evaluable_count {n} < {min_reg}")
            med = rm.get("median_return_pct")
            avg = rm.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{reg} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in regime_symbol_events[reg] if regime_symbol_events[reg][s] > 0})
        if n_sym > 1 and conc_by_regime[reg] > conc_max and pooled_counts.get(reg, 0) > 0:
            checklist_failures.append(f"{reg}: top-5 symbol concentration {conc_by_regime[reg]} > {conc_max}")

    return {
        "kind": "s1_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
        "symbols_with_data": sorted({s for ev in regime_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {
            "realized_vol_window": vol_w,
            "volume_z_window": vz_w,
            "regime_lookback_days": lookback,
            "regime_min_prior_days": min_prior,
            "merit_min_events_per_regime": min_reg,
            "merit_concentration_top5_max_pct": conc_max,
        },
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_regime": conc_by_regime,
        "baseline_metrics": baseline_metrics,
        "by_regime": regime_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s2_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
) -> dict[str, Any]:
    """Pooled S2 gap ecology over a fixed window + baseline + checklist (parallel to S1)."""
    settings = get_settings()
    ma_w = max(2, settings.daily_strategy_gap_ma_window)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)

    repo = PriceDataRepository(db)
    pooled_bucket: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in S2_BUCKET_KEYS}
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {k: 0 for k in S2_BUCKET_KEYS}
    bucket_symbol_events: dict[str, dict[str, int]] = {k: {} for k in S2_BUCKET_KEYS}
    skipped: list[dict[str, str]] = []

    for sym in symbols:
        symu = sym.strip().upper()
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s2_window_sample(
            bars,
            ma_w=ma_w,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for bkt in S2_BUCKET_KEYS:
            pooled_counts[bkt] += sample.counts.get(bkt, 0)
            for sy in sample.bucket_returns[bkt]:
                pooled_bucket[bkt][sy].extend(sample.bucket_returns[bkt][sy])
            n_ev = sample.counts.get(bkt, 0)
            if n_ev:
                bucket_symbol_events[bkt][symu] = bucket_symbol_events[bkt].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    bucket_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_bucket: dict[str, float] = {}
    for bkt, hmap in pooled_bucket.items():
        bucket_metrics[bkt] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[bkt] = {}
        conc_by_bucket[bkt] = _top5_concentration(bucket_symbol_events[bkt])
        for hk in hmap:
            bm_k = bucket_metrics[bkt][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = bm_k.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[bkt][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    for bkt in S2_BUCKET_KEYS:
        for hk in map(str, horizons):
            bm_k = bucket_metrics[bkt][hk]
            n = bm_k.get("evaluable_count", 0)
            if n < min_ev:
                checklist_failures.append(f"{bkt} horizon {hk}: evaluable_count {n} < {min_ev}")
            med = bm_k.get("median_return_pct")
            avg = bm_k.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{bkt} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in bucket_symbol_events[bkt] if bucket_symbol_events[bkt][s] > 0})
        if n_sym > 1 and conc_by_bucket[bkt] > conc_max and pooled_counts.get(bkt, 0) > 0:
            checklist_failures.append(f"{bkt}: top-5 symbol concentration {conc_by_bucket[bkt]} > {conc_max}")

    return {
        "kind": "s2_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
        "symbols_with_data": sorted({s for ev in bucket_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {"gap_ma_window": ma_w, "merit_min_events_per_bucket": min_ev},
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_bucket": conc_by_bucket,
        "baseline_metrics": baseline_metrics,
        "by_bucket": bucket_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s2_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rolling S2 merit (calendar or trading splits)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s2_merit_report(db, symbols, ws, we)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s2_merit_rolling(
        split_payloads,
        min_events_per_bucket=min_ev,
        horizons=horizons,
    )

    return {
        "kind": "s2_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def run_s4_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
) -> dict[str, Any]:
    """Pooled S4 calendar-flag buckets over a fixed window + baseline + checklist (parallel to S2)."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)
    inc_o = bool(getattr(settings, "s4_include_opex_week", True))
    inc_m = bool(getattr(settings, "s4_include_calendar_month_end", True))
    inc_q = bool(getattr(settings, "s4_include_quarter_end_calendar", True))

    repo = PriceDataRepository(db)
    pooled_bucket: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in S4_BUCKET_KEYS}
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {k: 0 for k in S4_BUCKET_KEYS}
    bucket_symbol_events: dict[str, dict[str, int]] = {k: {} for k in S4_BUCKET_KEYS}
    skipped: list[dict[str, str]] = []

    for sym in symbols:
        symu = sym.strip().upper()
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s4_window_sample(
            bars,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
            settings=settings,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for bkt in S4_BUCKET_KEYS:
            pooled_counts[bkt] += sample.counts.get(bkt, 0)
            for sy in sample.bucket_returns[bkt]:
                pooled_bucket[bkt][sy].extend(sample.bucket_returns[bkt][sy])
            n_ev = sample.counts.get(bkt, 0)
            if n_ev:
                bucket_symbol_events[bkt][symu] = bucket_symbol_events[bkt].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    bucket_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_bucket: dict[str, float] = {}
    for bkt, hmap in pooled_bucket.items():
        bucket_metrics[bkt] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[bkt] = {}
        conc_by_bucket[bkt] = _top5_concentration(bucket_symbol_events[bkt])
        for hk in hmap:
            bm_k = bucket_metrics[bkt][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = bm_k.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[bkt][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    if not (inc_o or inc_m or inc_q):
        checklist_failures.append("all S4 calendar dimensions disabled in config")
    for bkt in S4_BUCKET_KEYS:
        for hk in map(str, horizons):
            bm_k = bucket_metrics[bkt][hk]
            n = bm_k.get("evaluable_count", 0)
            if n < min_ev:
                checklist_failures.append(f"{bkt} horizon {hk}: evaluable_count {n} < {min_ev}")
            med = bm_k.get("median_return_pct")
            avg = bm_k.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{bkt} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in bucket_symbol_events[bkt] if bucket_symbol_events[bkt][s] > 0})
        if n_sym > 1 and conc_by_bucket[bkt] > conc_max and pooled_counts.get(bkt, 0) > 0:
            checklist_failures.append(f"{bkt}: top-5 symbol concentration {conc_by_bucket[bkt]} > {conc_max}")

    return {
        "kind": "s4_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
        "symbols_with_data": sorted({s for ev in bucket_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {
            "s4_include_opex_week": inc_o,
            "s4_include_calendar_month_end": inc_m,
            "s4_include_quarter_end_calendar": inc_q,
            "merit_min_events_per_bucket": min_ev,
            "merit_concentration_top5_max_pct": conc_max,
        },
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_bucket": conc_by_bucket,
        "baseline_metrics": baseline_metrics,
        "by_bucket": bucket_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s4_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rolling S4 merit (calendar or trading splits)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s4_merit_report(db, symbols, ws, we)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s4_merit_rolling(
        split_payloads,
        min_events_per_bucket=min_ev,
        horizons=horizons,
    )

    return {
        "kind": "s4_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def run_s3_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
) -> dict[str, Any]:
    """Pooled S3 vol term structure regimes over a fixed window + baseline + checklist."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)
    n_bk = max(2, min(20, int(settings.s3_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)

    repo = PriceDataRepository(db)
    pooled_regime: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {k: 0 for k in bucket_keys}
    regime_symbol_events: dict[str, dict[str, int]] = {k: {} for k in bucket_keys}
    skipped: list[dict[str, str]] = []

    for sym in symbols:
        symu = sym.strip().upper()
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s3_window_sample(
            db,
            bars,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for reg in bucket_keys:
            pooled_counts[reg] += sample.counts.get(reg, 0)
            for sy in sample.regime_returns[reg]:
                pooled_regime[reg][sy].extend(sample.regime_returns[reg][sy])
            n_ev = sample.counts.get(reg, 0)
            if n_ev:
                regime_symbol_events[reg][symu] = regime_symbol_events[reg].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    regime_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_regime: dict[str, float] = {}
    for reg, hmap in pooled_regime.items():
        regime_metrics[reg] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[reg] = {}
        conc_by_regime[reg] = _top5_concentration(regime_symbol_events[reg])
        for hk in hmap:
            rm = regime_metrics[reg][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = rm.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[reg][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    for reg in bucket_keys:
        for hk in map(str, horizons):
            rm = regime_metrics[reg][hk]
            n = rm.get("evaluable_count", 0)
            if n < min_ev:
                checklist_failures.append(f"{reg} horizon {hk}: evaluable_count {n} < {min_ev}")
            med = rm.get("median_return_pct")
            avg = rm.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{reg} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in regime_symbol_events[reg] if regime_symbol_events[reg][s] > 0})
        if n_sym > 1 and conc_by_regime[reg] > conc_max and pooled_counts.get(reg, 0) > 0:
            checklist_failures.append(f"{reg}: top-5 symbol concentration {conc_by_regime[reg]} > {conc_max}")

    return {
        "kind": "s3_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
        "symbols_with_data": sorted({s for ev in regime_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {
            "s3_feature_mode": settings.s3_feature_mode,
            "s3_regime_min_history_days": int(settings.s3_regime_min_history_days),
            "s3_regime_n_buckets": n_bk,
            "merit_min_events_per_regime": min_ev,
            "merit_concentration_top5_max_pct": conc_max,
        },
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_regime": conc_by_regime,
        "baseline_metrics": baseline_metrics,
        "by_regime": regime_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s3_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rolling S3 merit (calendar or trading splits)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    n_bk = max(2, min(20, int(settings.s3_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s3_merit_report(db, symbols, ws, we)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s3_merit_rolling(
        split_payloads,
        min_events_per_bucket=min_ev,
        horizons=horizons,
        bucket_keys=bucket_keys,
    )

    return {
        "kind": "s3_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def run_s5_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
) -> dict[str, Any]:
    """Pooled S5 cross-sectional dispersion quantile regimes over a fixed window + baseline + checklist.

    The merit symbol list is the **panel**: each symbol is evaluated with the same universe.
    """
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)
    n_bk = max(2, min(20, int(settings.s5_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)
    panel = list(dict.fromkeys(s.strip().upper() for s in symbols))

    repo = PriceDataRepository(db)
    pooled_regime: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {k: 0 for k in bucket_keys}
    regime_symbol_events: dict[str, dict[str, int]] = {k: {} for k in bucket_keys}
    skipped: list[dict[str, str]] = []

    for sym in panel:
        symu = sym.strip().upper()
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s5_window_sample(
            db,
            bars,
            panel,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for reg in bucket_keys:
            pooled_counts[reg] += sample.counts.get(reg, 0)
            for sy in sample.regime_returns[reg]:
                pooled_regime[reg][sy].extend(sample.regime_returns[reg][sy])
            n_ev = sample.counts.get(reg, 0)
            if n_ev:
                regime_symbol_events[reg][symu] = regime_symbol_events[reg].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    regime_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_regime: dict[str, float] = {}
    for reg, hmap in pooled_regime.items():
        regime_metrics[reg] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[reg] = {}
        conc_by_regime[reg] = _top5_concentration(regime_symbol_events[reg])
        for hk in hmap:
            rm = regime_metrics[reg][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = rm.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[reg][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    for reg in bucket_keys:
        for hk in map(str, horizons):
            rm = regime_metrics[reg][hk]
            n = rm.get("evaluable_count", 0)
            if n < min_ev:
                checklist_failures.append(f"{reg} horizon {hk}: evaluable_count {n} < {min_ev}")
            med = rm.get("median_return_pct")
            avg = rm.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{reg} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in regime_symbol_events[reg] if regime_symbol_events[reg][s] > 0})
        if n_sym > 1 and conc_by_regime[reg] > conc_max and pooled_counts.get(reg, 0) > 0:
            checklist_failures.append(f"{reg}: top-5 symbol concentration {conc_by_regime[reg]} > {conc_max}")

    return {
        "kind": "s5_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": panel,
        "symbols_with_data": sorted({s for ev in regime_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {
            "s5_min_symbols_cross_section": int(settings.s5_min_symbols_cross_section),
            "s5_regime_min_history_days": int(settings.s5_regime_min_history_days),
            "s5_regime_n_buckets": n_bk,
            "merit_min_events_per_regime": min_ev,
            "merit_concentration_top5_max_pct": conc_max,
        },
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_regime": conc_by_regime,
        "baseline_metrics": baseline_metrics,
        "by_regime": regime_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s5_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rolling S5 merit (calendar or trading splits)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    n_bk = max(2, min(20, int(settings.s5_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s5_merit_report(db, symbols, ws, we)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s3_merit_rolling(
        split_payloads,
        min_events_per_bucket=min_ev,
        horizons=horizons,
        bucket_keys=bucket_keys,
    )

    return {
        "kind": "s5_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def run_s6_merit_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    leg_b: str,
) -> dict[str, Any]:
    """Pooled S6 pair spread z regimes: each leg A in ``symbols`` vs fixed ``leg_b``."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    conc_max = float(settings.daily_strategy_merit_concentration_top5_max_pct)
    n_bk = max(2, min(20, int(settings.s6_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)
    leg_bu = leg_b.strip().upper()
    panel_a = [s.strip().upper() for s in symbols if s.strip().upper() != leg_bu]
    panel_a = list(dict.fromkeys(panel_a))

    repo = PriceDataRepository(db)
    pooled_regime: dict[str, dict[str, list[float]]] = {k: {str(h): [] for h in horizons} for k in bucket_keys}
    pooled_base: dict[str, list[float]] = {str(h): [] for h in horizons}
    pooled_counts: dict[str, int] = {k: 0 for k in bucket_keys}
    regime_symbol_events: dict[str, dict[str, int]] = {k: {} for k in bucket_keys}
    skipped: list[dict[str, str]] = []

    for symu in panel_a:
        rows = repo.list_for_stock(symu)
        bars = bars_from_price_rows(rows)
        sample = _compute_s6_window_sample(
            db,
            bars,
            symu,
            leg_bu,
            horizons=horizons,
            since=eval_start,
            until=eval_end,
        )
        if sample is None:
            skipped.append(
                {
                    "symbol": symu,
                    "reason": "insufficient_bars_or_no_eval_days",
                    "hint": _price_data_hint(db, symu, len(rows), len(bars)),
                }
            )
            continue
        for reg in bucket_keys:
            pooled_counts[reg] += sample.counts.get(reg, 0)
            for sy in sample.regime_returns[reg]:
                pooled_regime[reg][sy].extend(sample.regime_returns[reg][sy])
            n_ev = sample.counts.get(reg, 0)
            if n_ev:
                regime_symbol_events[reg][symu] = regime_symbol_events[reg].get(symu, 0) + n_ev
        for hk in pooled_base:
            pooled_base[hk].extend(sample.baseline_returns.get(hk, []))

    baseline_metrics = {hk: metrics_from_returns(rs) for hk, rs in pooled_base.items()}
    regime_metrics: dict[str, Any] = {}
    vs_baseline: dict[str, Any] = {}
    conc_by_regime: dict[str, float] = {}
    for reg, hmap in pooled_regime.items():
        regime_metrics[reg] = {hk: metrics_from_returns(rs) for hk, rs in hmap.items()}
        vs_baseline[reg] = {}
        conc_by_regime[reg] = _top5_concentration(regime_symbol_events[reg])
        for hk in hmap:
            rm = regime_metrics[reg][hk]
            bm = baseline_metrics.get(hk, {})
            ravg = rm.get("avg_return_pct", 0.0)
            bavg = bm.get("avg_return_pct", 0.0)
            vs_baseline[reg][hk] = {
                "avg_excess_vs_baseline_pct": round(ravg - bavg, 4),
                "baseline_avg_return_pct": bavg,
            }

    checklist_failures: list[str] = []
    for reg in bucket_keys:
        for hk in map(str, horizons):
            rm = regime_metrics[reg][hk]
            n = rm.get("evaluable_count", 0)
            if n < min_ev:
                checklist_failures.append(f"{reg} horizon {hk}: evaluable_count {n} < {min_ev}")
            med = rm.get("median_return_pct")
            avg = rm.get("avg_return_pct")
            if n >= 10 and med is not None and avg is not None and med * avg < 0:
                checklist_failures.append(f"{reg} horizon {hk}: median and avg disagree in sign")
        n_sym = len({s for s in regime_symbol_events[reg] if regime_symbol_events[reg][s] > 0})
        if n_sym > 1 and conc_by_regime[reg] > conc_max and pooled_counts.get(reg, 0) > 0:
            checklist_failures.append(f"{reg}: top-5 symbol concentration {conc_by_regime[reg]} > {conc_max}")

    return {
        "kind": "s6_merit_report",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": panel_a,
        "symbols_with_data": sorted({s for ev in regime_symbol_events.values() for s in ev}),
        "symbols_skipped": skipped,
        "params": {
            "leg_b": leg_bu,
            "s6_beta_window_days": int(settings.s6_beta_window_days),
            "s6_zscore_window_days": int(settings.s6_zscore_window_days),
            "s6_regime_min_history_days": int(settings.s6_regime_min_history_days),
            "s6_regime_n_buckets": n_bk,
            "merit_min_events_per_regime": min_ev,
            "merit_concentration_top5_max_pct": conc_max,
        },
        "horizons": list(horizons),
        "pooled_counts": pooled_counts,
        "concentration_top5_by_regime": conc_by_regime,
        "baseline_metrics": baseline_metrics,
        "by_regime": regime_metrics,
        "vs_baseline_avg_pct": vs_baseline,
        "checklist": {
            "pass": len(checklist_failures) == 0,
            "failures": checklist_failures,
            "note": "Minimum bar from SIGNAL_EVALUATION_CHECKLIST; passing does not imply tradable edge.",
        },
    }


def run_s6_merit_rolling_report(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    leg_b: str,
    n_splits: int,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Rolling S6 merit (calendar or trading splits)."""
    n_splits = max(1, int(n_splits))
    cal_syms = (
        list(trading_calendar_symbols) if trading_calendar_symbols is not None else [s.strip().upper() for s in symbols]
    )
    windows, mode_used = _merit_rolling_windows(db, eval_start, eval_end, n_splits, split_mode, cal_syms)
    settings = get_settings()
    min_ev = max(1, settings.daily_strategy_merit_min_events_per_regime)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    n_bk = max(2, min(20, int(settings.s6_regime_n_buckets)))
    bucket_keys = s3_bucket_keys(n_bk)
    leg_bu = leg_b.strip().upper()

    split_payloads: list[dict[str, Any]] = []
    for ws, we in windows:
        rep = run_s6_merit_report(db, symbols, ws, we, leg_b=leg_bu)
        split_payloads.append({"eval_window": {"start": str(ws), "end": str(we)}, "report": rep})

    rollup = _rollup_s3_merit_rolling(
        split_payloads,
        min_events_per_bucket=min_ev,
        horizons=horizons,
        bucket_keys=bucket_keys,
    )

    return {
        "kind": "s6_merit_report_rolling",
        "n_splits": len(windows),
        "split_mode_requested": split_mode,
        "split_mode_used": mode_used,
        "parent_window": {"start": str(eval_start), "end": str(eval_end)},
        "windows": [f"{a}..{b}" for a, b in windows],
        "splits": split_payloads,
        "rollup": rollup,
    }


def _strategy_merit_bundle_summary(
    strategy: StrategyMeritId,
    single: dict[str, Any],
    rolling: dict[str, Any] | None,
) -> dict[str, Any]:
    """Automated gate summary for a single-window + optional rolling merit bundle."""
    single_pass = single.get("checklist", {}).get("pass") is True
    rolling_included = rolling is not None
    rolling_pass: bool | None = None
    if rolling is not None:
        rolling_pass = rolling.get("rollup", {}).get("rolling_pass") is True

    gate_failures: list[str] = []
    if not single_pass:
        gate_failures.append("single_window_checklist_failed")
    if rolling_included and rolling_pass is False:
        gate_failures.append("rolling_stability_failed")

    if single_pass and rolling_included and rolling_pass:
        recommendation = "review_against_STRATEGY_CONCLUSION_FRAMEWORK"
    elif single_pass and not rolling_included:
        recommendation = "set_rolling_splits_ge_2_for_time_stability_or_accept_exploratory_only"
    else:
        recommendation = "exploratory_or_kill_fix_gates_first"

    return {
        "strategy": strategy,
        "single_window_checklist_pass": single_pass,
        "rolling_rollup_pass": rolling_pass,
        "rolling_included": rolling_included,
        "gate_failures": gate_failures,
        "all_automated_gates_pass": bool(single_pass and (rolling_pass is True if rolling_included else True)),
        "recommendation": recommendation,
        "note": "Automated gates only; costs, SPY adjustment, and ablations are manual "
        "(see docs/STRATEGY_CONCLUSION_FRAMEWORK.md).",
    }


def run_strategy_merit_bundle(
    db: Session,
    strategy: StrategyMeritId,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    rolling_splits: int = 5,
    split_mode: SplitMode = "trading",
    trading_calendar_symbols: Sequence[str] | None = None,
    pair_leg_b: str | None = None,
) -> dict[str, Any]:
    """One-shot strategy evaluation: pooled merit on **[eval_start, eval_end]** plus optional rolling stability.

    Use this as the default automation entrypoint for S1–S6 before deeper manual review.
    """
    rs = int(rolling_splits)
    cal_override = list(trading_calendar_symbols) if trading_calendar_symbols is not None else None
    pair_b_u = str(pair_leg_b).strip().upper() if pair_leg_b and str(pair_leg_b).strip() else None

    if strategy == "s1":
        single = run_s1_merit_report(db, symbols, eval_start, eval_end)
        rolling: dict[str, Any] | None = None
        if rs >= 2:
            rolling = run_s1_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    elif strategy == "s2":
        single = run_s2_merit_report(db, symbols, eval_start, eval_end)
        rolling = None
        if rs >= 2:
            rolling = run_s2_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    elif strategy == "s3":
        single = run_s3_merit_report(db, symbols, eval_start, eval_end)
        rolling = None
        if rs >= 2:
            rolling = run_s3_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    elif strategy == "s4":
        single = run_s4_merit_report(db, symbols, eval_start, eval_end)
        rolling = None
        if rs >= 2:
            rolling = run_s4_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    elif strategy == "s5":
        single = run_s5_merit_report(db, symbols, eval_start, eval_end)
        rolling = None
        if rs >= 2:
            rolling = run_s5_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    elif strategy == "s6":
        if not pair_b_u:
            raise ValueError("strategy s6 requires pair_leg_b (leg B ticker)")
        single = run_s6_merit_report(db, symbols, eval_start, eval_end, leg_b=pair_b_u)
        rolling = None
        if rs >= 2:
            rolling = run_s6_merit_rolling_report(
                db,
                symbols,
                eval_start,
                eval_end,
                leg_b=pair_b_u,
                n_splits=rs,
                split_mode=split_mode,
                trading_calendar_symbols=cal_override,
            )
    else:
        raise ValueError(f"unknown strategy merit id: {strategy!r}")

    summary = _strategy_merit_bundle_summary(strategy, single, rolling)
    return {
        "kind": "strategy_merit_bundle",
        "strategy": strategy,
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
        "pair_leg_b": pair_b_u if strategy == "s6" else None,
        "rolling_splits_configured": rs,
        "split_mode": split_mode,
        "single_window": single,
        "rolling": rolling,
        "summary": summary,
    }


def run_s1_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
) -> dict[str, Any]:
    """S1: volume vs realized-vol mismatch regimes vs forward close-to-close returns."""
    settings = get_settings()
    vol_w = max(2, settings.daily_strategy_realized_vol_window)
    vz_w = max(2, settings.daily_strategy_volume_z_window)
    lookback = max(20, settings.daily_strategy_regime_lookback_days)
    min_prior = max(10, settings.daily_strategy_regime_min_prior_days)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    repo = PriceDataRepository(db)
    rows = repo.list_for_stock(symbol)
    bars = bars_from_price_rows(rows)
    min_needed = max(vol_w, vz_w) + min_prior + max(horizons) + 5
    if len(bars) < min_needed:
        logger.warning(
            "S1: insufficient bars for %s (%s valid / %s raw rows, need %s)",
            symbol,
            len(bars),
            len(rows),
            min_needed,
        )
        return _empty_summary(
            "S1_volume_realized_vol_mismatch",
            symbol,
            since,
            until,
            horizons,
            hint=_price_data_hint(db, symbol, len(rows), len(bars)),
        )

    sample = _compute_s1_window_sample(
        bars,
        vol_w=vol_w,
        vz_w=vz_w,
        lookback=lookback,
        min_prior=min_prior,
        horizons=horizons,
        since=since,
        until=until,
    )
    if sample is None:
        return _empty_summary(
            "S1_volume_realized_vol_mismatch",
            symbol,
            since,
            until,
            horizons,
            hint="Internal error: S1 sample computation returned None after size check.",
        )

    summary_by: dict[str, Any] = {}
    for reg_key, hmap in sample.regime_returns.items():
        summary_by[reg_key] = {}
        for hk, rs in hmap.items():
            summary_by[reg_key][hk] = metrics_from_returns(rs)

    return {
        "strategy": "S1_volume_realized_vol_mismatch",
        "symbol": symbol,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {
            "realized_vol_window": vol_w,
            "volume_z_window": vz_w,
            "regime_lookback_days": lookback,
            "regime_min_prior_days": min_prior,
        },
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_regime": summary_by,
    }


def run_s2_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
) -> dict[str, Any]:
    """S2: gap vs prior close x trend bucket; forward returns from signal day's close."""
    settings = get_settings()
    ma_w = max(2, settings.daily_strategy_gap_ma_window)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    repo = PriceDataRepository(db)
    rows_buf = repo.list_for_stock(symbol)
    bars = bars_from_price_rows(rows_buf)
    min_s2 = ma_w + max(horizons) + 5
    if len(bars) < min_s2:
        return _empty_summary(
            "S2_gap_ecology",
            symbol,
            since,
            until,
            horizons,
            hint=_price_data_hint(db, symbol, len(rows_buf), len(bars)),
        )

    sample = _compute_s2_window_sample(bars, ma_w=ma_w, horizons=horizons, since=since, until=until)
    if sample is None:
        return _empty_summary(
            "S2_gap_ecology",
            symbol,
            since,
            until,
            horizons,
            hint="Internal error: S2 sample computation returned None after size check.",
        )

    summary_by: dict[str, Any] = {}
    for bname, hmap in sample.bucket_returns.items():
        summary_by[bname] = {}
        for hk, rs in hmap.items():
            summary_by[bname][hk] = metrics_from_returns(rs)

    return {
        "strategy": "S2_gap_ecology",
        "symbol": symbol,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {"gap_ma_window": ma_w},
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_bucket": summary_by,
    }


def run_s4_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
) -> dict[str, Any]:
    """S4: calendar-flag buckets (OpEx week, month-end, quarter-end) vs forward returns from signal close."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    inc_o = bool(getattr(settings, "s4_include_opex_week", True))
    inc_m = bool(getattr(settings, "s4_include_calendar_month_end", True))
    inc_q = bool(getattr(settings, "s4_include_quarter_end_calendar", True))

    repo = PriceDataRepository(db)
    rows_buf = repo.list_for_stock(symbol)
    bars = bars_from_price_rows(rows_buf)
    min_s4 = max(horizons) + 5
    if len(bars) < min_s4:
        return _empty_summary(
            "S4_calendar_events",
            symbol,
            since,
            until,
            horizons,
            hint=_price_data_hint(db, symbol, len(rows_buf), len(bars)),
        )
    if not (inc_o or inc_m or inc_q):
        return _empty_summary(
            "S4_calendar_events",
            symbol,
            since,
            until,
            horizons,
            hint="S4: all calendar dimensions disabled (s4_include_* config)",
        )

    sample = _compute_s4_window_sample(bars, horizons=horizons, since=since, until=until, settings=settings)
    if sample is None:
        return _empty_summary(
            "S4_calendar_events",
            symbol,
            since,
            until,
            horizons,
            hint="Internal error: S4 sample computation returned None after size check.",
        )

    summary_by: dict[str, Any] = {}
    for bname, hmap in sample.bucket_returns.items():
        summary_by[bname] = {}
        for hk, rs in hmap.items():
            summary_by[bname][hk] = metrics_from_returns(rs)

    return {
        "strategy": "S4_calendar_events",
        "symbol": symbol,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {
            "s4_include_opex_week": inc_o,
            "s4_include_calendar_month_end": inc_m,
            "s4_include_quarter_end_calendar": inc_q,
        },
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_bucket": summary_by,
    }


def run_s3_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
) -> dict[str, Any]:
    """S3: expanding quantile regimes on VIX/VIX3M feature vs forward equity returns."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)

    repo = PriceDataRepository(db)
    rows = repo.list_for_stock(symbol)
    bars = bars_from_price_rows(rows)
    min_needed = max(horizons) + 5
    if len(bars) < min_needed:
        logger.warning(
            "S3: insufficient bars for %s (%s valid / %s raw rows, need %s)",
            symbol,
            len(bars),
            len(rows),
            min_needed,
        )
        hint = _price_data_hint(db, symbol, len(rows), len(bars))
        base = _empty_summary("S3_vol_term_structure", symbol, since, until, horizons, hint=hint)
        return base

    sample = _compute_s3_window_sample(db, bars, horizons=horizons, since=since, until=until)
    if sample is None:
        return _empty_summary(
            "S3_vol_term_structure",
            symbol,
            since,
            until,
            horizons,
            hint="Internal error: S3 sample computation returned None after size check.",
        )

    summary_by: dict[str, Any] = {}
    for reg_key, hmap in sample.regime_returns.items():
        summary_by[reg_key] = {}
        for hk, rs in hmap.items():
            summary_by[reg_key][hk] = metrics_from_returns(rs)

    n_bk = max(2, min(20, int(settings.s3_regime_n_buckets)))

    return {
        "strategy": "S3_vol_term_structure",
        "symbol": symbol,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {
            "s3_feature_mode": settings.s3_feature_mode,
            "s3_regime_min_history_days": int(settings.s3_regime_min_history_days),
            "s3_regime_n_buckets": n_bk,
        },
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_regime": summary_by,
    }


def run_s5_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
    *,
    panel_universe: Sequence[str] | None = None,
) -> dict[str, Any]:
    """S5: expanding quantile regimes on cross-sectional return dispersion vs forward returns for one symbol."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    symu = symbol.strip().upper()
    panel = list(dict.fromkeys(s.strip().upper() for s in (panel_universe or [symu])))

    repo = PriceDataRepository(db)
    rows = repo.list_for_stock(symu)
    bars = bars_from_price_rows(rows)
    min_needed = daily_strategy_min_valid_bars("s5")
    if len(bars) < min_needed:
        logger.warning(
            "S5: insufficient bars for %s (%s valid / %s raw rows, need %s)",
            symu,
            len(bars),
            len(rows),
            min_needed,
        )
        hint = _price_data_hint(db, symu, len(rows), len(bars))
        return _empty_summary("S5_cross_sectional_dispersion", symu, since, until, horizons, hint=hint)

    sample = _compute_s5_window_sample(db, bars, panel, horizons=horizons, since=since, until=until)
    if sample is None:
        return _empty_summary(
            "S5_cross_sectional_dispersion",
            symu,
            since,
            until,
            horizons,
            hint="S5: insufficient panel history, bars, or eval window (see s5_* config and panel_universe).",
        )

    summary_by: dict[str, Any] = {}
    for reg_key, hmap in sample.regime_returns.items():
        summary_by[reg_key] = {}
        for hk, rs in hmap.items():
            summary_by[reg_key][hk] = metrics_from_returns(rs)

    n_bk = max(2, min(20, int(settings.s5_regime_n_buckets)))

    return {
        "strategy": "S5_cross_sectional_dispersion",
        "symbol": symu,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {
            "panel_universe": panel,
            "s5_min_symbols_cross_section": int(settings.s5_min_symbols_cross_section),
            "s5_regime_min_history_days": int(settings.s5_regime_min_history_days),
            "s5_regime_n_buckets": n_bk,
        },
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_regime": summary_by,
    }


def run_s6_evaluation(
    db: Session,
    symbol: str,
    since: date | None,
    until: date | None,
    *,
    pair_leg_b: str,
) -> dict[str, Any]:
    """S6: pair spread z-score quantile regimes vs forward returns on leg A (subject symbol)."""
    settings = get_settings()
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    symu = symbol.strip().upper()
    leg_b = str(pair_leg_b).strip().upper()

    repo = PriceDataRepository(db)
    rows = repo.list_for_stock(symu)
    bars = bars_from_price_rows(rows)
    min_needed = daily_strategy_min_valid_bars("s6")
    if len(bars) < min_needed:
        logger.warning(
            "S6: insufficient bars for leg A %s (%s valid / %s raw rows, need %s)",
            symu,
            len(bars),
            len(rows),
            min_needed,
        )
        hint = _price_data_hint(db, symu, len(rows), len(bars))
        return _empty_summary("S6_slow_pairs", symu, since, until, horizons, hint=hint)

    sample = _compute_s6_window_sample(
        db,
        bars,
        symu,
        leg_b,
        horizons=horizons,
        since=since,
        until=until,
    )
    if sample is None:
        return _empty_summary(
            "S6_slow_pairs",
            symu,
            since,
            until,
            horizons,
            hint="S6: insufficient overlap with leg B or regime history (see s6_* config and pair_leg_b).",
        )

    summary_by: dict[str, Any] = {}
    for reg_key, hmap in sample.regime_returns.items():
        summary_by[reg_key] = {}
        for hk, rs in hmap.items():
            summary_by[reg_key][hk] = metrics_from_returns(rs)

    n_bk = max(2, min(20, int(settings.s6_regime_n_buckets)))

    return {
        "strategy": "S6_slow_pairs",
        "symbol": symu,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "params": {
            "leg_b": leg_b,
            "s6_beta_window_days": int(settings.s6_beta_window_days),
            "s6_zscore_window_days": int(settings.s6_zscore_window_days),
            "s6_regime_min_history_days": int(settings.s6_regime_min_history_days),
            "s6_regime_n_buckets": n_bk,
        },
        "horizons": list(horizons),
        "counts": sample.counts,
        "by_regime": summary_by,
    }


def _empty_summary(
    strategy: str,
    symbol: str,
    since: date | None,
    until: date | None,
    horizons: tuple[int, ...],
    *,
    hint: str | None = None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "strategy": strategy,
        "symbol": symbol,
        "date_range": {"start": str(since) if since else None, "end": str(until) if until else None},
        "horizons": list(horizons),
        "error": "insufficient_price_data",
        "counts": {},
    }
    if hint:
        base["hint"] = hint
    if "S1" in strategy or strategy.startswith("S3") or strategy.startswith("S5") or strategy.startswith("S6"):
        base["by_regime"] = {}
    else:
        base["by_bucket"] = {}
    return base

"""Daily-frequency strategy research (STRATEGY_EXPLORATION S1, S2).

Pure feature construction and forward-return summaries from daily OHLCV only.
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
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.services.leader_follower_evaluation_service import compute_forward_return

logger = logging.getLogger(__name__)

SplitMode = Literal["calendar", "trading"]
StrategyMeritId = Literal["s1", "s2"]


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


@dataclass(frozen=True)
class DailyStrategySymbolDataAssessment:
    """Result of a read-only data sufficiency check for S1/S2 daily strategy eval."""

    symbol: str
    status: Literal["ready", "missing_stock", "insufficient_history"]
    message: str | None
    min_bars_required: int
    valid_bar_count: int
    raw_price_row_count: int


def daily_strategy_min_valid_bars(strategy: StrategyMeritId) -> int:
    """Minimum valid daily bars required (same contract as _compute_s1/_compute_s2)."""
    settings = get_settings()
    if strategy == "s1":
        vol_w = max(2, settings.daily_strategy_realized_vol_window)
        vz_w = max(2, settings.daily_strategy_volume_z_window)
        min_prior = max(10, settings.daily_strategy_regime_min_prior_days)
        horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
        return max(vol_w, vz_w) + min_prior + max(horizons) + 5
    ma_w = max(2, settings.daily_strategy_gap_ma_window)
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    return ma_w + max(horizons) + 5


def assess_daily_strategy_symbol_data(
    db: Session,
    symbol: str,
    strategy: StrategyMeritId,
    eval_start: date | None,
    eval_end: date | None,
) -> DailyStrategySymbolDataAssessment:
    """Check whether ``price_data`` and ``stocks`` support evaluation for one symbol.

    Uses the same feature windows and :func:`_compute_s1_window_sample` /
    :func:`_compute_s2_window_sample` paths as merit and single-symbol eval.
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


def _calendar_splits(start: date, end: date, n: int) -> list[tuple[date, date]]:
    """Partition [start, end] into ``n`` contiguous calendar sub-ranges (inclusive)."""
    if n <= 1:
        return [(start, end)]
    if start > end:
        raise ValueError("start must be <= end")
    total_days = (end - start).days + 1
    if total_days < n:
        return [(start, end)]
    base, rem = divmod(total_days, n)
    out: list[tuple[date, date]] = []
    cur = start
    for i in range(n):
        seg_days = base + (1 if i < rem else 0)
        if seg_days <= 0:
            break
        seg_end = cur + timedelta(days=seg_days - 1)
        if seg_end > end:
            seg_end = end
        out.append((cur, seg_end))
        cur = seg_end + timedelta(days=1)
        if cur > end:
            break
    return out if out else [(start, end)]


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


def _trading_day_chunks(sorted_days: list[date], n: int) -> list[tuple[date, date]]:
    """Partition sorted trading days into ``n`` contiguous index blocks; each block is [first, last] date."""
    if not sorted_days:
        return []
    if n <= 1:
        return [(sorted_days[0], sorted_days[-1])]
    L = len(sorted_days)
    base, rem = divmod(L, n)
    out: list[tuple[date, date]] = []
    idx = 0
    for i in range(n):
        take = base + (1 if i < rem else 0)
        if take <= 0:
            continue
        chunk = sorted_days[idx : idx + take]
        if chunk:
            out.append((chunk[0], chunk[-1]))
        idx += take
    return out if out else [(sorted_days[0], sorted_days[-1])]


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
        return (_calendar_splits(eval_start, eval_end, n_splits), "calendar")
    days = _load_union_trading_days(db, trading_calendar_symbols, eval_start, eval_end)
    if not days:
        return (
            _calendar_splits(eval_start, eval_end, n_splits),
            "calendar(fallback_no_trading_days_in_union)",
        )
    return (_trading_day_chunks(days, n_splits), "trading")


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
) -> dict[str, Any]:
    """One-shot strategy evaluation: pooled merit on **[eval_start, eval_end]** plus optional rolling stability.

    Use this as the default automation entrypoint for S1/S2 before deeper manual review.
    """
    rs = int(rolling_splits)
    cal_override = list(trading_calendar_symbols) if trading_calendar_symbols is not None else None

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
    else:
        raise ValueError(f"unknown strategy merit id: {strategy!r}")

    summary = _strategy_merit_bundle_summary(strategy, single, rolling)
    return {
        "kind": "strategy_merit_bundle",
        "strategy": strategy,
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": [s.strip().upper() for s in symbols],
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
    if "S1" in strategy:
        base["by_regime"] = {}
    else:
        base["by_bucket"] = {}
    return base

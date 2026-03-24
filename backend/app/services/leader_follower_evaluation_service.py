"""Evaluate leader-follower signals: forward returns, summary metrics, pair aggregates.

Uses trading-day logic (consistent with label_service). Computed on demand; no persistence.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.leader_follower_signal import LeaderFollowerSignal

logger = logging.getLogger(__name__)

DEFAULT_HORIZONS = (1, 3, 5)


def _get_horizons() -> tuple[int, ...]:
    """Return evaluation horizons from config."""
    raw = get_settings().leader_follower_evaluation_horizons
    if not raw or not isinstance(raw, str):
        return DEFAULT_HORIZONS
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return DEFAULT_HORIZONS
    try:
        return tuple(sorted(set(int(h) for h in parts if int(h) > 0)))
    except (ValueError, TypeError):
        return DEFAULT_HORIZONS


def _get_overlap_window() -> int:
    """Return overlap window in trading days."""
    return max(1, get_settings().leader_follower_evaluation_overlap_window_days)


def _load_price_by_symbol(
    price_repo: PriceDataRepository,
    symbols: set[str],
    start_date: date,
    end_date: date,
) -> dict[str, list[tuple[date, float]]]:
    """Load close prices for symbols in date range. Returns symbol -> sorted (date, close)."""
    rows = price_repo.list_in_date_range(start_date, end_date)
    by_symbol: dict[str, dict[date, float]] = defaultdict(dict)
    for p in rows:
        if p.stock_symbol in symbols:
            by_symbol[p.stock_symbol][p.date] = float(p.close)
    result: dict[str, list[tuple[date, float]]] = {}
    for sym, date_to_close in by_symbol.items():
        result[sym] = sorted((d, c) for d, c in date_to_close.items() if c and c > 0)
    return result


def compute_forward_return(
    symbol: str,
    ref_date: date,
    horizon_days: int,
    price_by_symbol: dict[str, list[tuple[date, float]]],
) -> float | None:
    """Compute forward return for symbol from ref_date over horizon_days trading sessions.

    Returns (close[target] / close[ref_date] - 1) * 100 as percent, or None if data missing.
    """
    dates_closes = price_by_symbol.get(symbol)
    if not dates_closes:
        return None
    dates = [d for d, _ in dates_closes]
    idx_map = {d: i for i, d in enumerate(dates)}
    if ref_date not in idx_map:
        return None
    i = idx_map[ref_date]
    j = i + horizon_days
    if j >= len(dates):
        return None
    target_date = dates[j]
    date_to_close = dict(dates_closes)
    close_ref = date_to_close.get(ref_date)
    close_target = date_to_close.get(target_date)
    if close_ref is None or close_target is None or close_ref == 0:
        return None
    fwd = (close_target / close_ref) - 1.0
    return round(fwd * 100.0, 4)


def get_entry_price(
    symbol: str,
    signal_date: date,
    price_by_symbol: dict[str, list[tuple[date, float]]],
) -> float | None:
    """Get follower close on signal_date (entry price). Returns None if missing."""
    dates_closes = price_by_symbol.get(symbol)
    if not dates_closes:
        return None
    date_to_close = dict(dates_closes)
    close = date_to_close.get(signal_date)
    if close is None or close <= 0:
        return None
    return round(float(close), 2)


def evaluate_signal(
    signal: LeaderFollowerSignal,
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    """Evaluate a single signal: entry price and horizon outcomes."""
    follower = signal.follower_symbol
    sig_date = signal.signal_date
    entry = get_entry_price(follower, sig_date, price_by_symbol)
    horizon_outcomes: dict[str, dict[str, Any]] = {}
    for h in horizons:
        fwd = compute_forward_return(follower, sig_date, h, price_by_symbol)
        if fwd is not None:
            horizon_outcomes[str(h) + "d"] = {
                "forward_return_pct": fwd,
                "win": fwd > 0,
            }
        else:
            horizon_outcomes[str(h) + "d"] = {"forward_return_pct": None, "win": None}
    created_at = signal.created_at
    if created_at is not None and hasattr(created_at, "isoformat"):
        created_str = created_at.isoformat()
    else:
        created_str = str(created_at) if created_at else ""
    return {
        "id": signal.id,
        "signal_date": sig_date.isoformat() if hasattr(sig_date, "isoformat") else str(sig_date),
        "created_at": created_str,
        "leader_symbol": signal.leader_symbol,
        "follower_symbol": follower,
        "entry_price": entry,
        **{k: v for k, v in horizon_outcomes.items()},
    }


def compute_duplicate_overlap(
    signals: Sequence[LeaderFollowerSignal],
    window_days: int,
) -> dict[str, Any]:
    """Count signals that are repeats (same pair within window, calendar days)."""
    if not signals:
        return {"repeat_pair_in_window": 0, "window_days": window_days}
    sorted_sigs = sorted(signals, key=lambda s: (s.signal_date, s.id))
    repeat_count = 0
    for i, s in enumerate(sorted_sigs):
        pair = (s.leader_symbol, s.follower_symbol)
        for j in range(i - 1, -1, -1):
            prev = sorted_sigs[j]
            if (prev.leader_symbol, prev.follower_symbol) != pair:
                continue
            delta = (s.signal_date - prev.signal_date).days
            if 0 < delta <= window_days:
                repeat_count += 1
                break
    return {"repeat_pair_in_window": repeat_count, "window_days": window_days}


def aggregate_summary(
    signals: Sequence[LeaderFollowerSignal],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    overlap_window: int | None = None,
) -> dict[str, Any]:
    """Aggregate summary metrics: total_signals, signals_per_day, by_horizon, duplicate_overlap."""
    if overlap_window is None:
        overlap_window = _get_overlap_window()
    total = len(signals)
    date_range: dict[str, str | None] = {"since": None, "until": None}
    if signals:
        dates = [s.signal_date for s in signals]
        date_range["since"] = min(dates).isoformat()
        date_range["until"] = max(dates).isoformat()
    days = 1.0
    if date_range["since"] and date_range["until"]:
        try:
            since_d = date.fromisoformat(date_range["since"] or "")
            until_d = date.fromisoformat(date_range["until"] or "")
            days = max(1.0, (until_d - since_d).days + 1)
        except (ValueError, TypeError):
            pass
    signals_per_day = round(total / days, 2) if total else 0.0

    by_horizon: dict[str, dict[str, Any]] = {}
    for h in horizons:
        key = f"{h}d"
        returns: list[float] = []
        for s in signals:
            fwd = compute_forward_return(s.follower_symbol, s.signal_date, h, price_by_symbol)
            if fwd is not None:
                returns.append(fwd)
        evaluable = len(returns)
        if evaluable == 0:
            by_horizon[key] = {
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
                "median_return_pct": 0.0,
                "evaluable_count": 0,
            }
        else:
            wins = sum(1 for r in returns if r > 0)
            avg = round(sum(returns) / evaluable, 4)
            sorted_r = sorted(returns)
            mid = evaluable // 2
            median = sorted_r[mid] if evaluable % 2 else (sorted_r[mid - 1] + sorted_r[mid]) / 2
            median = round(median, 4)
            by_horizon[key] = {
                "win_rate": round(wins / evaluable, 4),
                "avg_return_pct": avg,
                "median_return_pct": median,
                "evaluable_count": evaluable,
            }

    duplicate_overlap = compute_duplicate_overlap(signals, overlap_window)
    return {
        "total_signals": total,
        "signals_per_day": signals_per_day,
        "date_range": date_range,
        "by_horizon": by_horizon,
        "duplicate_overlap": duplicate_overlap,
    }


def aggregate_by_pair(
    signals: Sequence[LeaderFollowerSignal],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[dict[str, Any]]:
    """Aggregate by (leader, follower) pair with per-horizon metrics."""
    pair_to_signals: dict[tuple[str, str], list[LeaderFollowerSignal]] = defaultdict(list)
    for s in signals:
        pair_to_signals[(s.leader_symbol, s.follower_symbol)].append(s)
    result: list[dict[str, Any]] = []
    for (leader, follower), sigs in pair_to_signals.items():
        returns_by_h: dict[int, list[float]] = {h: [] for h in horizons}
        for s in sigs:
            for h in horizons:
                fwd = compute_forward_return(follower, s.signal_date, h, price_by_symbol)
                if fwd is not None:
                    returns_by_h[h].append(fwd)
        h_metrics: dict[str, dict[str, float]] = {}
        for h in horizons:
            rs = returns_by_h[h]
            if not rs:
                h_metrics[f"{h}d"] = {"win_rate": 0.0, "avg_return_pct": 0.0}
            else:
                wins = sum(1 for r in rs if r > 0)
                h_metrics[f"{h}d"] = {
                    "win_rate": round(wins / len(rs), 4),
                    "avg_return_pct": round(sum(rs) / len(rs), 4),
                }
        result.append(
            {
                "leader_symbol": leader,
                "follower_symbol": follower,
                "signal_count": len(sigs),
                **h_metrics,
            }
        )
    return result


def filter_pairs_by_thresholds(
    pairs: list[dict[str, Any]],
    min_signal_count: int,
    min_avg_return_1d: float,
    min_win_rate_1d: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filter pairs by thresholds. Returns (passing_pairs, all_pairs_with_status).

    Each pair gets filter_status: 'pass' | 'fail' | 'insufficient_data'.
    """
    thresholds = {
        "min_signal_count": min_signal_count,
        "min_avg_return_1d": min_avg_return_1d,
        "min_win_rate_1d": min_win_rate_1d,
    }
    passing: list[dict[str, Any]] = []
    with_status: list[dict[str, Any]] = []
    for p in pairs:
        p_copy = dict(p)
        p_copy["thresholds_applied"] = thresholds
        sc = p_copy.get("signal_count", 0)
        h1 = p_copy.get("1d", {}) or {}
        avg_1d = float(h1.get("avg_return_pct", 0) or 0)
        win_1d = float(h1.get("win_rate", 0) or 0)
        if sc < min_signal_count:
            p_copy["filter_status"] = "insufficient_data"
        elif avg_1d < min_avg_return_1d or win_1d < min_win_rate_1d:
            p_copy["filter_status"] = "fail"
        else:
            p_copy["filter_status"] = "pass"
            passing.append(p_copy)
        with_status.append(p_copy)
    return passing, with_status


def rank_pairs(
    pairs: list[dict[str, Any]],
    sort_by: str = "avg_return_1d",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    """Sort pairs by chosen metric. sort_by: avg_return_1d, win_rate_1d, signal_count, avg_return_3d, avg_return_5d."""
    horizon: str | None
    metric: str
    horizon, metric = "1d", "avg_return_pct"
    if sort_by == "win_rate_1d":
        horizon, metric = "1d", "win_rate"
    elif sort_by == "signal_count":
        horizon, metric = None, "signal_count"
    elif sort_by == "avg_return_3d":
        horizon, metric = "3d", "avg_return_pct"
    elif sort_by == "avg_return_5d":
        horizon, metric = "5d", "avg_return_pct"
    else:
        horizon, metric = "1d", "avg_return_pct"

    def key(p: dict[str, Any]) -> float | int:
        if horizon is None:
            return p.get("signal_count", 0) or 0
        h = p.get(horizon, {}) or {}
        val = h.get(metric, 0) or 0
        return float(val) if isinstance(val, (int, float)) else 0

    reverse = sort_order.lower() != "asc"
    return sorted(pairs, key=key, reverse=reverse)


def run_evaluation(
    db: Session,
    since_date: date | None = None,
    until_date: date | None = None,
    leader: str | None = None,
    follower: str | None = None,
    limit: int = 500,
) -> tuple[
    list[LeaderFollowerSignal],
    dict[str, list[tuple[date, float]]],
    tuple[int, ...],
]:
    """Load signals and price data for evaluation. Returns (signals, price_by_symbol, horizons)."""
    signal_repo = LeaderFollowerSignalRepository(db)
    price_repo = PriceDataRepository(db)
    signals = signal_repo.list_signals(
        limit=limit,
        since_date=since_date,
        until_date=until_date,
        leader=leader,
        follower=follower,
    )
    if not signals:
        return ([], {}, _get_horizons())
    symbols = {s.follower_symbol for s in signals}
    min_d = min(s.signal_date for s in signals)
    max_d = max(s.signal_date for s in signals)
    buf = timedelta(days=max(_get_horizons()) * 3)
    end = max_d + buf
    price_by_symbol = _load_price_by_symbol(price_repo, symbols, min_d, end)
    return (list(signals), price_by_symbol, _get_horizons())

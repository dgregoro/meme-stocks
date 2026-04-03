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
from backend.app.services.research_eval_db_guard import require_research_eval_db_has_prices
from backend.app.services.research_execution.costs import (
    apply_round_trip_cost,
    round_trip_cost_pct_from_bps,
)

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

    # Event-level metrics: group by (leader, date), avg follower return per event, then aggregate
    by_event_horizon = _aggregate_by_event(signals, price_by_symbol, horizons)
    total_events = by_event_horizon.get("total_events", 0)
    days_ev = 1.0
    if date_range["since"] and date_range["until"]:
        try:
            since_d = date.fromisoformat(date_range["since"] or "")
            until_d = date.fromisoformat(date_range["until"] or "")
            days_ev = max(1.0, (until_d - since_d).days + 1)
        except (ValueError, TypeError):
            pass
    events_per_day = round(total_events / days_ev, 2) if total_events else 0.0

    return {
        "total_signals": total,
        "total_events": total_events,
        "signals_per_day": signals_per_day,
        "events_per_day": events_per_day,
        "date_range": date_range,
        "by_horizon": by_horizon,
        "by_event": by_event_horizon.get("by_event", {}),
        "duplicate_overlap": duplicate_overlap,
    }


def _aggregate_by_event(
    signals: Sequence[LeaderFollowerSignal],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    """Compute event-level metrics. Event = (leader_symbol, signal_date).

    For each event: average follower returns across all signals in that event.
    Event wins if avg_return > 0.
    Returns total_events, by_event (per-horizon: event_win_rate, event_avg_return_pct, event_count).
    """
    event_to_signals: dict[tuple[str, date], list[LeaderFollowerSignal]] = defaultdict(list)
    for s in signals:
        event_to_signals[(s.leader_symbol, s.signal_date)].append(s)

    if not event_to_signals:
        return {
            "total_events": 0,
            "by_event": {
                f"{h}d": {"event_win_rate": 0.0, "event_avg_return_pct": 0.0, "event_count": 0} for h in horizons
            },
        }

    by_event: dict[str, dict[str, Any]] = {}
    for h in horizons:
        event_returns: list[float] = []
        for (leader, sig_date), sigs in event_to_signals.items():
            returns: list[float] = []
            for s in sigs:
                fwd = compute_forward_return(s.follower_symbol, sig_date, h, price_by_symbol)
                if fwd is not None:
                    returns.append(fwd)
            if returns:
                event_avg = sum(returns) / len(returns)
                event_returns.append(event_avg)
        key = f"{h}d"
        if not event_returns:
            by_event[key] = {"event_win_rate": 0.0, "event_avg_return_pct": 0.0, "event_count": 0}
        else:
            wins = sum(1 for r in event_returns if r > 0)
            by_event[key] = {
                "event_win_rate": round(wins / len(event_returns), 4),
                "event_avg_return_pct": round(sum(event_returns) / len(event_returns), 4),
                "event_count": len(event_returns),
            }
    return {"total_events": len(event_to_signals), "by_event": by_event}


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


def collect_b1_control_returns(
    follower: str,
    event_date: date,
    horizon_days: int,
    price_by_symbol: dict[str, list[tuple[date, float]]],
    leader_event_dates: set[date],
    eval_since: date,
    eval_until: date,
) -> list[float]:
    """B1 control pool: follower forward returns on non-event days matching DOW.

    Control day ``T`` must satisfy: ``eval_since <= T <= eval_until``, same weekday as
    ``event_date``, ``T != event_date``, and ``T`` not in ``leader_event_dates`` (no
    qualified leader event for that leader on ``T``). Regime matching is not applied until
    the pipeline exposes a shared regime series (see docs/PRIMARY_HYPOTHESIS.md).
    """
    series = price_by_symbol.get(follower) or []
    out: list[float] = []
    for ref_date, _ in series:
        if ref_date < eval_since or ref_date > eval_until:
            continue
        if ref_date.weekday() != event_date.weekday():
            continue
        if ref_date == event_date:
            continue
        if ref_date in leader_event_dates:
            continue
        r = compute_forward_return(follower, ref_date, horizon_days, price_by_symbol)
        if r is not None:
            out.append(r)
    return out


def _leader_event_dates_in_window(
    db: Session,
    since: date,
    until: date,
) -> dict[str, set[date]]:
    """All signal dates per leader in ``[since, until]`` (any follower)."""
    repo = LeaderFollowerSignalRepository(db)
    rows = repo.list_signals(limit=None, since_date=since, until_date=until)
    by_leader: dict[str, set[date]] = defaultdict(set)
    for s in rows:
        by_leader[s.leader_symbol].add(s.signal_date)
    return dict(by_leader)


def _b1_resolve_round_trip_cost_bps(explicit_bps: float | None) -> tuple[float, str]:
    if explicit_bps is not None:
        return float(explicit_bps), "parameter"
    bps = float(get_settings().research_default_round_trip_cost_bps)
    return bps, "research_default_round_trip_cost_bps"


def _b1_costs_report_dict(bps: float, source: str) -> dict[str, Any]:
    cost_pct = round_trip_cost_pct_from_bps(bps)
    return {
        "round_trip_cost_bps": bps,
        "round_trip_cost_pct": round(cost_pct, 6),
        "source": source,
        "paper_sim_alignment": (
            "python -m backend.app.cli simulate leader-follower --cost_pct: round-trip in percentage "
            f"points; {bps:g} bps == --cost_pct {cost_pct:g}."
        ),
    }


def run_evaluation(
    db: Session,
    since_date: date | None = None,
    until_date: date | None = None,
    leader: str | None = None,
    follower: str | None = None,
    limit: int | None = 500,
) -> tuple[
    list[LeaderFollowerSignal],
    dict[str, list[tuple[date, float]]],
    tuple[int, ...],
]:
    """Load signals and price data for evaluation. Returns (signals, price_by_symbol, horizons).

    ``limit`` ``None`` loads all matching signals (ordered newest first). Non-``None`` caps count.
    """
    require_research_eval_db_has_prices(db)
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


def build_event_arm_pair_aggregates(
    db: Session,
    since_date: date | None = None,
    until_date: date | None = None,
    *,
    leader: str | None = None,
    follower: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Treatment-arm-only pair aggregates (event-day follower forwards).

    Used for H1 Step 3. Does **not** compute baseline B1. ``limit`` ``None`` = all matching
    signals (repository order: newest first).
    """
    signals, price_by, horizons = run_evaluation(
        db,
        since_date,
        until_date,
        leader,
        follower,
        limit,
    )
    pairs = aggregate_by_pair(signals, price_by, horizons)
    return {
        "kind": "leader_follower_event_arm",
        "since": str(since_date) if since_date else None,
        "until": str(until_date) if until_date else None,
        "leader_filter": leader,
        "follower_filter": follower,
        "signal_count": len(signals),
        "horizons": list(horizons),
        "pairs": pairs,
    }


def build_b1_excess_pair_aggregates(
    db: Session,
    since_date: date | None = None,
    until_date: date | None = None,
    *,
    leader: str | None = None,
    follower: str | None = None,
    limit: int | None = None,
    round_trip_cost_bps: float | None = None,
    window_role: str | None = None,
) -> dict[str, Any]:
    """H1 Steps 4–5: B1 baseline excess plus **net** arms using research round-trip cost.

    Gross excess at horizon *h* is ``event_fwd_pct - mean(control_fwd_pct)``. Net applies
    ``apply_round_trip_cost`` (same as ``research_execution`` / paper sim) to event and to
    each signal's baseline mean; **symmetric** one round-trip per arm implies
    ``avg_net_excess_pct == avg_excess_pct``.

    ``round_trip_cost_bps``: override; default ``research_default_round_trip_cost_bps``.
    ``window_role``: optional label e.g. ``\"holdout\"`` for JSON only (use date range as hold-out).

    ``limit`` ``None`` evaluates all matching signals (repository order: newest first).
    """
    cost_bps, cost_src = _b1_resolve_round_trip_cost_bps(round_trip_cost_bps)
    costs_payload = _b1_costs_report_dict(cost_bps, cost_src)
    cost_pct = round_trip_cost_pct_from_bps(cost_bps)

    eval_ctx: dict[str, Any] = {
        "window_role": window_role,
        "step_5_note": (
            "Report avg_net_* fields for execution read; use --start/--end as preregistered hold-out "
            "for primary decisions (Step 6 adds train/validate/test discipline)."
        ),
    }

    signals, _, horizons = run_evaluation(
        db,
        since_date,
        until_date,
        leader,
        follower,
        limit,
    )
    if not signals:
        return {
            "kind": "leader_follower_b1_excess",
            "baseline": "B1_DOW_matched_non_event",
            "since": str(since_date) if since_date else None,
            "until": str(until_date) if until_date else None,
            "leader_filter": leader,
            "follower_filter": follower,
            "signal_count": 0,
            "horizons": list(_get_horizons()),
            "costs": costs_payload,
            "evaluation_context": eval_ctx,
            "by_horizon": {},
            "pairs": [],
            "note": (
                "No signals in range. Costs metadata is still the research default (or override). "
                "Regime matching pending pipeline support."
            ),
        }

    eff_since = since_date if since_date is not None else min(s.signal_date for s in signals)
    eff_until = until_date if until_date is not None else max(s.signal_date for s in signals)
    leader_calendar = _leader_event_dates_in_window(db, eff_since, eff_until)

    price_repo = PriceDataRepository(db)
    followers = {s.follower_symbol for s in signals}
    buf = timedelta(days=max(horizons) * 3)
    price_by = _load_price_by_symbol(price_repo, followers, eff_since, eff_until + buf)

    pair_to_excess: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(lambda: {hi: [] for hi in horizons})
    pair_to_event: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(lambda: {hi: [] for hi in horizons})
    pair_to_baseline: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(lambda: {hi: [] for hi in horizons})
    pair_to_signals: dict[tuple[str, str], list[LeaderFollowerSignal]] = defaultdict(list)
    for s in signals:
        pair_to_signals[(s.leader_symbol, s.follower_symbol)].append(s)

    by_horizon: dict[str, dict[str, Any]] = {}

    for h in horizons:
        key = f"{h}d"
        excess_vals: list[float] = []
        event_vals: list[float] = []
        base_vals: list[float] = []
        skip_no_event = 0
        skip_no_baseline = 0
        for s in signals:
            ev_dates = leader_calendar.get(s.leader_symbol, set())
            event_r = compute_forward_return(s.follower_symbol, s.signal_date, h, price_by)
            if event_r is None:
                skip_no_event += 1
                continue
            controls = collect_b1_control_returns(
                s.follower_symbol,
                s.signal_date,
                h,
                price_by,
                ev_dates,
                eff_since,
                eff_until,
            )
            if not controls:
                skip_no_baseline += 1
                continue
            baseline_mean = sum(controls) / len(controls)
            excess = round(float(event_r) - float(baseline_mean), 4)
            excess_vals.append(excess)
            event_vals.append(float(event_r))
            base_vals.append(float(baseline_mean))
            pair_to_excess[(s.leader_symbol, s.follower_symbol)][h].append(excess)
            pair_to_event[(s.leader_symbol, s.follower_symbol)][h].append(float(event_r))
            pair_to_baseline[(s.leader_symbol, s.follower_symbol)][h].append(float(baseline_mean))

        n = len(excess_vals)
        if n == 0:
            by_horizon[key] = {
                "evaluable_excess_count": 0,
                "avg_excess_pct": None,
                "median_excess_pct": None,
                "avg_event_return_pct": None,
                "avg_baseline_mean_pct": None,
                "avg_net_event_return_pct": None,
                "avg_net_baseline_mean_pct": None,
                "avg_net_excess_pct": None,
                "median_net_excess_pct": None,
                "skip_no_event_return": skip_no_event,
                "skip_no_baseline": skip_no_baseline,
            }
        else:
            net_event_vals = [apply_round_trip_cost(ev, cost_pct) for ev in event_vals]
            net_base_vals = [apply_round_trip_cost(bv, cost_pct) for bv in base_vals]
            net_excess_vals = [round(ne - nb, 4) for ne, nb in zip(net_event_vals, net_base_vals)]
            sorted_e = sorted(excess_vals)
            mid = n // 2
            median_e = sorted_e[mid] if n % 2 == 1 else round((sorted_e[mid - 1] + sorted_e[mid]) / 2.0, 4)
            sorted_ne = sorted(net_excess_vals)
            median_ne = sorted_ne[mid] if n % 2 == 1 else round((sorted_ne[mid - 1] + sorted_ne[mid]) / 2.0, 4)
            by_horizon[key] = {
                "evaluable_excess_count": n,
                "avg_excess_pct": round(sum(excess_vals) / n, 4),
                "median_excess_pct": median_e,
                "avg_event_return_pct": round(sum(event_vals) / n, 4),
                "avg_baseline_mean_pct": round(sum(base_vals) / n, 4),
                "avg_net_event_return_pct": round(sum(net_event_vals) / n, 4),
                "avg_net_baseline_mean_pct": round(sum(net_base_vals) / n, 4),
                "avg_net_excess_pct": round(sum(net_excess_vals) / n, 4),
                "median_net_excess_pct": median_ne,
                "skip_no_event_return": skip_no_event,
                "skip_no_baseline": skip_no_baseline,
            }

    pairs_out: list[dict[str, Any]] = []
    for (ldr, flw), sigs in sorted(pair_to_signals.items()):
        by_h = pair_to_excess.get((ldr, flw), {hi: [] for hi in horizons})
        ev_h = pair_to_event.get((ldr, flw), {hi: [] for hi in horizons})
        bs_h = pair_to_baseline.get((ldr, flw), {hi: [] for hi in horizons})
        row: dict[str, Any] = {
            "leader_symbol": ldr,
            "follower_symbol": flw,
            "signal_count": len(sigs),
        }
        for h in horizons:
            xs = by_h.get(h) or []
            hk = f"{h}d"
            if not xs:
                row[hk] = {
                    "evaluable_excess_count": 0,
                    "avg_excess_pct": 0.0,
                    "median_excess_pct": 0.0,
                    "avg_net_event_return_pct": 0.0,
                    "avg_net_baseline_mean_pct": 0.0,
                    "avg_net_excess_pct": 0.0,
                    "median_net_excess_pct": 0.0,
                }
            else:
                evs = ev_h.get(h) or []
                bss = bs_h.get(h) or []
                sx = sorted(xs)
                m = len(sx) // 2
                med = sx[m] if len(sx) % 2 == 1 else round((sx[m - 1] + sx[m]) / 2.0, 4)
                ne = [apply_round_trip_cost(e, cost_pct) for e in evs]
                nb = [apply_round_trip_cost(b, cost_pct) for b in bss]
                nx = [round(a - b, 4) for a, b in zip(ne, nb)]
                sm = len(nx) // 2
                med_n = nx[sm] if len(nx) % 2 == 1 else round((nx[sm - 1] + nx[sm]) / 2.0, 4)
                row[hk] = {
                    "evaluable_excess_count": len(xs),
                    "avg_excess_pct": round(sum(xs) / len(xs), 4),
                    "median_excess_pct": med,
                    "avg_net_event_return_pct": round(sum(ne) / len(ne), 4),
                    "avg_net_baseline_mean_pct": round(sum(nb) / len(nb), 4),
                    "avg_net_excess_pct": round(sum(nx) / len(nx), 4),
                    "median_net_excess_pct": med_n,
                }
        pairs_out.append(row)

    note = (
        f"Steps 4–5: gross excess vs B1 mean; net arms subtract one round-trip "
        f"({cost_bps:g} bps). Symmetric cost => avg_net_excess_pct equals avg_excess_pct. "
        "Regime bucket matching is not applied until available in the evaluation pipeline."
    )

    return {
        "kind": "leader_follower_b1_excess",
        "baseline": "B1_DOW_matched_non_event",
        "since": str(eff_since),
        "until": str(eff_until),
        "leader_filter": leader,
        "follower_filter": follower,
        "signal_count": len(signals),
        "horizons": list(horizons),
        "costs": costs_payload,
        "evaluation_context": eval_ctx,
        "by_horizon": by_horizon,
        "pairs": pairs_out,
        "note": note,
    }

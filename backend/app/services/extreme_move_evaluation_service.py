"""On-demand forward-return evaluation for extreme move events (016)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.extreme_move_event_repo import ExtremeMoveEventRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.services.leader_follower_evaluation_service import compute_forward_return
from backend.app.services.research_execution.costs import round_trip_cost_pct_from_bps

DEFAULT_HORIZONS = (1, 3, 5)


def _parse_horizons() -> tuple[int, ...]:
    raw = get_settings().extreme_move_research_horizons
    if not raw or not isinstance(raw, str):
        return DEFAULT_HORIZONS
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return DEFAULT_HORIZONS
    try:
        return tuple(sorted(set(int(h) for h in parts if int(h) > 0)))
    except (ValueError, TypeError):
        return DEFAULT_HORIZONS


def _load_price_by_symbol(
    price_repo: PriceDataRepository,
    symbols: set[str],
    start_date: date,
    end_date: date,
) -> dict[str, list[tuple[date, float]]]:
    rows = price_repo.list_in_date_range(start_date, end_date)
    by_symbol: dict[str, dict[date, float]] = defaultdict(dict)
    for p in rows:
        if p.stock_symbol in symbols:
            by_symbol[p.stock_symbol][p.date] = float(p.close)
    result: dict[str, list[tuple[date, float]]] = {}
    for sym, date_to_close in by_symbol.items():
        result[sym] = sorted((d, c) for d, c in date_to_close.items() if c and c > 0)
    return result


def _metrics_from_returns(returns: list[float]) -> dict[str, Any]:
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


def run_extreme_move_evaluation(
    db: Session,
    since_date: date | None = None,
    until_date: date | None = None,
    symbol: str | None = None,
    limit: int = 500,
) -> tuple[list[ExtremeMoveEvent], dict[str, list[tuple[date, float]]], tuple[int, ...]]:
    repo = ExtremeMoveEventRepository(db)
    price_repo = PriceDataRepository(db)
    horizons = _parse_horizons()
    events = repo.list_for_evaluation(
        symbol=symbol,
        since_date=since_date,
        until_date=until_date,
        limit=limit,
    )
    if not events:
        return ([], {}, horizons)
    symbols = {e.symbol for e in events}
    min_d = min(e.event_date for e in events)
    max_d = max(e.event_date for e in events)
    buf = timedelta(days=max(horizons) * 3)
    end_load = max_d + buf
    price_by_symbol = _load_price_by_symbol(price_repo, symbols, min_d, end_load)
    return (events, price_by_symbol, horizons)


def aggregate_extreme_move_summary(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    if horizons is None:
        horizons = _parse_horizons()
    date_range: dict[str, str | None] = {"since": None, "until": None}
    if events:
        dates = [e.event_date for e in events]
        date_range["since"] = min(dates).isoformat()
        date_range["until"] = max(dates).isoformat()

    by_horizon: dict[str, dict[str, Any]] = {}
    for h in horizons:
        key = f"{h}d"
        returns: list[float] = []
        for e in events:
            fwd = compute_forward_return(e.symbol, e.event_date, h, price_by_symbol)
            if fwd is not None:
                returns.append(fwd)
        by_horizon[key] = _metrics_from_returns(returns)

    by_event_type: dict[str, dict[str, dict[str, Any]]] = {}
    for et in ("extreme_up", "extreme_down"):
        by_event_type[et] = {}
        for h in horizons:
            key = f"{h}d"
            returns = []
            for e in events:
                if e.event_type != et:
                    continue
                fwd = compute_forward_return(e.symbol, e.event_date, h, price_by_symbol)
                if fwd is not None:
                    returns.append(fwd)
            by_event_type[et][key] = _metrics_from_returns(returns)

    return {
        "total_events": len(events),
        "date_range": date_range,
        "forward_anchor": "event_date_close",
        "horizons_trading_days": list(horizons),
        "by_horizon": by_horizon,
        "by_event_type": by_event_type,
    }


def aggregate_by_symbol(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
    min_sample: int = 1,
) -> list[dict[str, Any]]:
    if horizons is None:
        horizons = _parse_horizons()
    sym_to_events: dict[str, list[ExtremeMoveEvent]] = defaultdict(list)
    for e in events:
        sym_to_events[e.symbol].append(e)
    out: list[dict[str, Any]] = []
    for sym, evs in sorted(sym_to_events.items(), key=lambda x: x[0]):
        if len(evs) < min_sample:
            continue
        row: dict[str, Any] = {"symbol": sym, "event_count": len(evs), "by_horizon": {}}
        for h in horizons:
            key = f"{h}d"
            returns: list[float] = []
            for e in evs:
                fwd = compute_forward_return(sym, e.event_date, h, price_by_symbol)
                if fwd is not None:
                    returns.append(fwd)
            row["by_horizon"][key] = _metrics_from_returns(returns)
        out.append(row)
    return out


def aggregate_by_type_flat(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    summary = aggregate_extreme_move_summary(events, price_by_symbol, horizons)
    return summary["by_event_type"]  # type: ignore[no-any-return]


def aggregate_evaluation_by_magnitude(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Per-magnitude-bucket evaluation summaries (017)."""
    if horizons is None:
        horizons = _parse_horizons()
    buckets: dict[str, list[ExtremeMoveEvent]] = defaultdict(list)
    for e in events:
        buckets[e.magnitude_bucket or "unknown"].append(e)
    return {k: aggregate_extreme_move_summary(v, price_by_symbol, horizons) for k, v in sorted(buckets.items())}


def aggregate_evaluation_by_volume(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Per-volume-bucket evaluation summaries (017)."""
    if horizons is None:
        horizons = _parse_horizons()
    buckets: dict[str, list[ExtremeMoveEvent]] = defaultdict(list)
    for e in events:
        buckets[e.volume_bucket or "unknown"].append(e)
    return {k: aggregate_extreme_move_summary(v, price_by_symbol, horizons) for k, v in sorted(buckets.items())}


def aggregate_evaluation_by_magnitude_volume(
    events: Sequence[ExtremeMoveEvent],
    price_by_symbol: dict[str, list[tuple[date, float]]],
    horizons: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Combined magnitude|volume key, e.g. ``5-8|high`` (017)."""
    if horizons is None:
        horizons = _parse_horizons()
    buckets: dict[str, list[ExtremeMoveEvent]] = defaultdict(list)
    for e in events:
        mb = e.magnitude_bucket or "unknown"
        vb = e.volume_bucket or "unknown"
        buckets[f"{mb}|{vb}"].append(e)
    return {k: aggregate_extreme_move_summary(v, price_by_symbol, horizons) for k, v in sorted(buckets.items())}


_Q_START = ((1, 1), (4, 1), (7, 1), (10, 1))
_Q_END = ((3, 31), (6, 30), (9, 30), (12, 31))


def calendar_quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    """Inclusive calendar quarter ``[start, end]`` (UTC date). ``quarter`` ∈ {1,2,3,4}."""
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1–4")
    sm, sd = _Q_START[quarter - 1]
    em, ed = _Q_END[quarter - 1]
    return date(year, sm, sd), date(year, em, ed)


def iter_train_calendar_quarters(train_end_exclusive: date) -> list[tuple[str, date, date]]:
    """Quarters whose last calendar day is strictly before ``train_end_exclusive``.

    Scans a bounded window of calendar years so empty early years are cheap to skip at query time.
    """
    out: list[tuple[str, date, date]] = []
    y_min = max(1990, train_end_exclusive.year - 30)
    for y in range(y_min, train_end_exclusive.year + 1):
        for q in (1, 2, 3, 4):
            start, end = calendar_quarter_bounds(y, q)
            if end >= train_end_exclusive:
                continue
            out.append((f"{y}-Q{q}", start, end))
    return out


def h2_stability_brittle_verdict(
    *,
    eligible_quarters: int,
    eligible_non_positive_net: int,
) -> bool:
    """``True`` if strict majority of eligible quarters have mean net K ≤ 0 (`docs/H2_HYPOTHESIS.md`)."""
    if eligible_quarters <= 0:
        return False
    return eligible_non_positive_net * 2 > eligible_quarters


def run_h2_quarterly_stability_extreme_down(
    db: Session,
    *,
    train_end_exclusive: date,
    horizon_k: int = 5,
    min_evaluable: int = 20,
    list_limit: int = 100_000,
) -> dict[str, Any]:
    """Train-only calendar-quarter mean net at ``horizon_k`` for ``extreme_down`` (H2 Step 7)."""
    if horizon_k < 1:
        raise ValueError("horizon_k must be >= 1")
    if min_evaluable < 1:
        raise ValueError("min_evaluable must be >= 1")

    settings = get_settings()
    cost_pct = round_trip_cost_pct_from_bps(float(settings.research_default_round_trip_cost_bps))

    repo = ExtremeMoveEventRepository(db)
    price_repo = PriceDataRepository(db)

    min_train_d = db.scalar(
        select(func.min(ExtremeMoveEvent.event_date)).where(
            ExtremeMoveEvent.event_type == "extreme_down",
            ExtremeMoveEvent.event_date < train_end_exclusive,
        )
    )
    if min_train_d is None:
        return {
            "hypothesis_doc": "H2_HYPOTHESIS.md preregistered stability",
            "train_end_exclusive": train_end_exclusive.isoformat(),
            "horizon_k": horizon_k,
            "min_evaluable_per_quarter": min_evaluable,
            "round_trip_cost_bps": float(settings.research_default_round_trip_cost_bps),
            "cost_pct_points": cost_pct,
            "quarters": [],
            "eligible_quarter_count": 0,
            "eligible_mean_net_non_positive_count": 0,
            "brittle_per_majority_rule": False,
            "verdict": "inconclusive",
            "note": "no extreme_down rows with event_date < train_end_exclusive (backfill or DB path)",
        }

    quarter_defs = [
        row
        for row in iter_train_calendar_quarters(train_end_exclusive)
        if row[2] >= min_train_d  # quarter end on/after first train event
    ]

    per_quarter: list[dict[str, Any]] = []
    for label, q_start, q_end in quarter_defs:
        events = list(
            repo.list_filtered(
                symbol=None,
                since_date=q_start,
                until_date=q_end,
                event_type="extreme_down",
                limit=list_limit,
                offset=0,
            )
        )
        if not events:
            per_quarter.append(
                {
                    "quarter": label,
                    "start": q_start.isoformat(),
                    "end": q_end.isoformat(),
                    "raw_event_count": 0,
                    "evaluable_count": 0,
                    "mean_gross_pct": None,
                    "mean_net_pct": None,
                    "omitted_from_vote": True,
                    "omit_reason": "no_events",
                }
            )
            continue

        symbols = {e.symbol for e in events}
        min_d = min(e.event_date for e in events)
        max_d = max(e.event_date for e in events)
        buf = timedelta(days=horizon_k * 3)
        price_by_symbol = _load_price_by_symbol(price_repo, symbols, min_d, max_d + buf)

        gross: list[float] = []
        for e in events:
            fwd = compute_forward_return(e.symbol, e.event_date, horizon_k, price_by_symbol)
            if fwd is not None:
                gross.append(fwd)

        n = len(gross)
        mean_g = round(sum(gross) / n, 6) if n else None
        mean_n = round(mean_g - cost_pct, 6) if n and mean_g is not None else None
        omitted = n < min_evaluable
        per_quarter.append(
            {
                "quarter": label,
                "start": q_start.isoformat(),
                "end": q_end.isoformat(),
                "raw_event_count": len(events),
                "evaluable_count": n,
                "mean_gross_pct": mean_g,
                "mean_net_pct": mean_n,
                "omitted_from_vote": omitted,
                "omit_reason": None if not omitted else "evaluable_below_min",
            }
        )

    eligible = [r for r in per_quarter if not r["omitted_from_vote"]]
    non_pos = sum(1 for r in eligible if r["mean_net_pct"] is not None and r["mean_net_pct"] <= 0)
    n_eligible = len(eligible)
    brittle = h2_stability_brittle_verdict(
        eligible_quarters=n_eligible,
        eligible_non_positive_net=non_pos,
    )

    inconclusive = n_eligible == 0

    return {
        "hypothesis_doc": "H2_HYPOTHESIS.md preregistered stability",
        "train_end_exclusive": train_end_exclusive.isoformat(),
        "horizon_k": horizon_k,
        "min_evaluable_per_quarter": min_evaluable,
        "round_trip_cost_bps": float(settings.research_default_round_trip_cost_bps),
        "cost_pct_points": cost_pct,
        "quarters": per_quarter,
        "eligible_quarter_count": n_eligible,
        "eligible_mean_net_non_positive_count": non_pos,
        "brittle_per_majority_rule": brittle,
        "verdict": "inconclusive" if inconclusive else ("brittle" if brittle else "not_brittle"),
    }

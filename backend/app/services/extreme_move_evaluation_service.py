"""On-demand forward-return evaluation for extreme move events (016)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.extreme_move_event_repo import ExtremeMoveEventRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.extreme_move_event import ExtremeMoveEvent
from backend.app.services.leader_follower_evaluation_service import compute_forward_return

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

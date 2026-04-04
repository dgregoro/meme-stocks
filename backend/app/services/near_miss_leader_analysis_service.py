"""Near-miss leader research: forward qualified-leader rate after threshold-failure days.

Uses persisted ``LeaderDebugEvaluation`` rows (replay or scheduled runs) and
``LeaderEvent`` for outcomes. Trading-session horizons use each symbol's
``price_data`` date set (sorted unique dates).
"""

from __future__ import annotations

import bisect
import json
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.models.job_run_history import JobRunHistory
from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation
from backend.app.models.leader_event import LeaderEvent
from backend.app.utils.errors import DataAccessError

logger = logging.getLogger(__name__)

DEFAULT_JOB_NAMES = ("leader_follower_replay", "leader_follower_detection")


def _parse_event_date_from_metrics(metrics_json: str | None) -> date | None:
    if not metrics_json:
        return None
    try:
        m = json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError):
        return None
    raw = m.get("event_date")
    if raw is None:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _is_near_miss_evaluation(ev: LeaderDebugEvaluation) -> bool:
    return ev.qualified_as_leader is False and ev.return_pct is not None and ev.volume_ratio is not None


def run_near_miss_upgrade_analysis(
    db: Session,
    *,
    since_date: date,
    until_date: date,
    horizon_sessions: int,
    job_names: tuple[str, ...] = DEFAULT_JOB_NAMES,
) -> dict[str, Any]:
    """Count near-miss symbol-days and how many later qualify as leaders within H sessions.

    **Near-miss:** non-qualified evaluation with both ``return_pct`` and ``volume_ratio``
    (same operational definition as ``near_miss_count`` in leader-follower detection).

    **Upgrade:** exists ``LeaderEvent`` for the symbol with ``event_date`` strictly after
    the near-miss calendar day and on or before the H-th later trading day that has a
    bar for that symbol in ``price_data``.

    Rows with fewer than ``horizon_sessions`` future trading days in ``price_data`` are
    counted in ``incomplete_horizon`` and excluded from ``eligible`` and the rate.
    """
    if since_date > until_date:
        raise ValueError("since_date must be <= until_date")
    if horizon_sessions < 1 or horizon_sessions > 252:
        raise ValueError("horizon_sessions must be in [1, 252]")

    try:
        stmt = (
            select(JobRunHistory)
            .where(
                JobRunHistory.job_name.in_(job_names),
                JobRunHistory.success.is_(True),
            )
            .order_by(JobRunHistory.id.asc())
        )
        runs = list(db.execute(stmt).scalars().all())
    except SQLAlchemyError as exc:
        logger.error("near_miss_upgrade: failed to list job runs: %s", exc)
        raise DataAccessError("Failed to list job runs for near-miss analysis") from exc

    run_ids: list[int] = []
    run_id_to_event_date: dict[int, date] = {}
    for run in runs:
        ed = _parse_event_date_from_metrics(getattr(run, "metrics_json", None))
        if ed is None or ed < since_date or ed > until_date:
            continue
        run_ids.append(run.id)
        run_id_to_event_date[run.id] = ed

    if not run_ids:
        return {
            "since_date": since_date.isoformat(),
            "until_date": until_date.isoformat(),
            "horizon_sessions": horizon_sessions,
            "job_names": list(job_names),
            "runs_in_window": 0,
            "near_miss_rows_raw": 0,
            "near_miss_symbol_days_unique": 0,
            "eligible": 0,
            "incomplete_horizon": 0,
            "upgrades_within_horizon": 0,
            "upgrade_rate": None,
        }

    try:
        ev_stmt = (
            select(LeaderDebugEvaluation)
            .where(LeaderDebugEvaluation.job_run_id.in_(run_ids))
            .order_by(LeaderDebugEvaluation.id.asc())
        )
        evaluations = list(db.execute(ev_stmt).scalars().all())
    except SQLAlchemyError as exc:
        logger.error("near_miss_upgrade: failed to list evaluations: %s", exc)
        raise DataAccessError("Failed to list leader debug evaluations") from exc

    near_miss_rows_raw = 0
    # Dedupe by (symbol, event_date); first row wins (stable by evaluation id order).
    unique_key_to_symbol_date: dict[tuple[str, date], tuple[str, date]] = {}
    for ev in evaluations:
        if not _is_near_miss_evaluation(ev):
            continue
        ed = run_id_to_event_date.get(ev.job_run_id)
        if ed is None:
            continue
        near_miss_rows_raw += 1
        sym = ev.stock_symbol.upper()
        key = (sym, ed)
        if key not in unique_key_to_symbol_date:
            unique_key_to_symbol_date[key] = (sym, ed)

    nm_list = list(unique_key_to_symbol_date.values())
    symbols = sorted({s for s, _ in nm_list})
    price_repo = PriceDataRepository(db)
    symbol_trading: dict[str, list[date]] = {}
    for sym in symbols:
        try:
            symbol_trading[sym] = price_repo.list_dates_for_symbol(sym)
        except SQLAlchemyError as exc:
            logger.error("near_miss_upgrade: price dates failed for %s: %s", sym, exc)
            raise DataAccessError(f"Failed to list trading dates for {sym}") from exc

    # Calendar cap for loading leader events (trading horizon can span weekends/holidays).
    cal_buffer_end = until_date + timedelta(days=max(horizon_sessions * 5, 40))
    try:
        le_stmt = (
            select(LeaderEvent)
            .where(
                LeaderEvent.leader_symbol.in_(symbols),
                LeaderEvent.event_date > since_date,
                LeaderEvent.event_date <= cal_buffer_end,
            )
            .order_by(LeaderEvent.leader_symbol.asc(), LeaderEvent.event_date.asc())
        )
        leader_rows = list(db.execute(le_stmt).scalars().all())
    except SQLAlchemyError as exc:
        logger.error("near_miss_upgrade: failed to list leader events: %s", exc)
        raise DataAccessError("Failed to list leader events") from exc

    leader_dates_by_symbol: dict[str, list[date]] = {s: [] for s in symbols}
    for row in leader_rows:
        sym = row.leader_symbol.upper()
        if sym not in leader_dates_by_symbol:
            continue
        dates_list = leader_dates_by_symbol[sym]
        if not dates_list or dates_list[-1] != row.event_date:
            dates_list.append(row.event_date)

    eligible = 0
    incomplete = 0
    upgrades = 0
    for sym, d0 in nm_list:
        trading = symbol_trading.get(sym, [])
        i = bisect.bisect_left(trading, d0)
        if i >= len(trading) or trading[i] != d0:
            incomplete += 1
            continue
        nxt = trading[i + 1 : i + 1 + horizon_sessions]
        if len(nxt) < horizon_sessions:
            incomplete += 1
            continue
        d_hi = nxt[-1]
        eligible += 1
        ld = leader_dates_by_symbol.get(sym, [])
        if _leader_upgrade_in_window(ld, d0, d_hi):
            upgrades += 1

    rate: float | None
    if eligible > 0:
        rate = upgrades / eligible
    else:
        rate = None

    return {
        "since_date": since_date.isoformat(),
        "until_date": until_date.isoformat(),
        "horizon_sessions": horizon_sessions,
        "job_names": list(job_names),
        "runs_in_window": len(run_ids),
        "near_miss_rows_raw": near_miss_rows_raw,
        "near_miss_symbol_days_unique": len(nm_list),
        "eligible": eligible,
        "incomplete_horizon": incomplete,
        "upgrades_within_horizon": upgrades,
        "upgrade_rate": rate,
    }


def _leader_upgrade_in_window(leader_dates: list[date], d_after: date, d_hi: date) -> bool:
    j = bisect.bisect_right(leader_dates, d_after)
    return j < len(leader_dates) and leader_dates[j] <= d_hi

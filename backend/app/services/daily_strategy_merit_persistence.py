"""Persist merit / bundle JSON reports from the evaluate daily-strategy CLI."""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.daily_strategy_merit_run_repo import DailyStrategyMeritRunRepository
from backend.app.models.daily_strategy_merit_run import DailyStrategyMeritRun

logger = logging.getLogger(__name__)


def _flags_from_report(report: dict[str, Any]) -> tuple[bool | None, bool | None, bool | None]:
    """Return (checklist_pass, rolling_pass, all_gates_pass) for quick filtering."""
    kind = report.get("kind")
    cp: bool | None = None
    rp: bool | None = None
    ag: bool | None = None
    if kind in ("s1_merit_report", "s2_merit_report", "s3_merit_report", "s4_merit_report"):
        raw = report.get("checklist", {}).get("pass")
        cp = bool(raw) if raw is not None else None
    elif kind in (
        "s1_merit_report_rolling",
        "s2_merit_report_rolling",
        "s3_merit_report_rolling",
        "s4_merit_report_rolling",
    ):
        raw = report.get("rollup", {}).get("rolling_pass")
        rp = bool(raw) if raw is not None else None
    elif kind == "strategy_merit_bundle":
        summ = report.get("summary") or {}
        raw_ag = summ.get("all_automated_gates_pass")
        ag = bool(raw_ag) if raw_ag is not None else None
        raw_cp = summ.get("single_window_checklist_pass")
        cp = bool(raw_cp) if raw_cp is not None else None
        raw_rp = summ.get("rolling_rollup_pass")
        rp = bool(raw_rp) if raw_rp is not None else None
    return cp, rp, ag


def _strategy_id_from_report(report: dict[str, Any]) -> str:
    kind = report.get("kind")
    if kind == "strategy_merit_bundle":
        s = report.get("strategy")
        if isinstance(s, str) and s:
            return s.strip().lower()
    if isinstance(kind, str) and kind.startswith("s1_"):
        return "s1"
    if isinstance(kind, str) and kind.startswith("s2_"):
        return "s2"
    if isinstance(kind, str) and kind.startswith("s3_"):
        return "s3"
    if isinstance(kind, str) and kind.startswith("s4_"):
        return "s4"
    return "unknown"


def _eval_window(report: dict[str, Any]) -> tuple[Any, Any]:
    ew = report.get("eval_window") or {}
    if isinstance(ew, dict) and ew.get("start") and ew.get("end"):
        return ew.get("start"), ew.get("end")
    pw = report.get("parent_window") or {}
    if isinstance(pw, dict) and pw.get("start") and pw.get("end"):
        return pw.get("start"), pw.get("end")
    return None, None


def _n_splits(report: dict[str, Any]) -> int:
    kind = report.get("kind")
    if kind in (
        "s1_merit_report_rolling",
        "s2_merit_report_rolling",
        "s3_merit_report_rolling",
        "s4_merit_report_rolling",
    ):
        return int(report.get("n_splits") or 1)
    if kind == "strategy_merit_bundle":
        return max(1, int(report.get("rolling_splits_configured") or 1))
    return 1


def _split_mode(report: dict[str, Any]) -> str | None:
    kind = report.get("kind")
    if kind in (
        "s1_merit_report_rolling",
        "s2_merit_report_rolling",
        "s3_merit_report_rolling",
        "s4_merit_report_rolling",
    ):
        sm = report.get("split_mode_requested")
        return str(sm) if sm is not None else None
    if kind == "strategy_merit_bundle":
        sm = report.get("split_mode")
        return str(sm) if sm is not None else None
    return None


def _symbols_list(report: dict[str, Any]) -> list[str]:
    raw = report.get("symbols_requested")
    if isinstance(raw, list):
        return [str(s).strip().upper() for s in raw if str(s).strip()]
    return []


def _parse_d(d: Any) -> dt.date:
    if isinstance(d, dt.date) and not isinstance(d, dt.datetime):
        return d
    if isinstance(d, dt.datetime):
        return d.date()
    s = str(d).strip()[:10]
    return dt.date.fromisoformat(s)


def build_merit_run_row(report: dict[str, Any]) -> DailyStrategyMeritRun:
    kind = str(report.get("kind") or "unknown")
    sid = _strategy_id_from_report(report)
    start_s, end_s = _eval_window(report)
    if start_s is None or end_s is None:
        raise ValueError("report missing eval_window / parent_window start/end")
    es = _parse_d(start_s)
    ee = _parse_d(end_s)

    syms = _symbols_list(report)
    cp, rp, ag = _flags_from_report(report)
    payload = json.dumps(report, default=str)
    return DailyStrategyMeritRun(
        report_kind=kind[:64],
        strategy_id=sid[:8],
        eval_start=es,
        eval_end=ee,
        n_splits=_n_splits(report),
        split_mode=_split_mode(report),
        symbol_count=len(syms),
        symbols_json=json.dumps(syms, default=str),
        report_json=payload,
        checklist_pass=cp,
        rolling_pass=rp,
        all_gates_pass=ag,
    )


def try_persist_merit_report(
    session: Session,
    report: dict[str, Any],
    *,
    skip: bool = False,
) -> int | None:
    """Insert one row and commit. Returns new id, or None if skipped/failed (logs on failure)."""
    if skip:
        return None
    if not get_settings().daily_strategy_merit_persist_runs:
        return None
    try:
        row = build_merit_run_row(report)
    except Exception as exc:
        logger.warning("Merit run not persisted (invalid report shape): %s", exc)
        return None
    try:
        repo = DailyStrategyMeritRunRepository(session)
        repo.add(row)
        session.commit()
        return int(row.id)
    except Exception as exc:
        logger.error("Failed to persist daily strategy merit run: %s", exc, exc_info=True)
        try:
            session.rollback()
        except Exception as rb_exc:
            logger.warning("Session rollback after merit persist failure failed: %s", rb_exc)
        return None

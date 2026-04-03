"""Run S1–S6 merit bundles plus S7 rule search and persist each to ``daily_strategy_merit_runs``."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.services.daily_frequency_strategy_research import (
    SplitMode,
    StrategyMeritId,
    bars_from_price_rows,
    run_strategy_merit_bundle,
)
from backend.app.services.daily_strategy_merit_persistence import try_persist_merit_report
from backend.app.services.s7_rule_discovery import build_feature_rows_from_bars, run_rule_search

logger = logging.getLogger(__name__)

_STRATEGIES_S1_S6: tuple[StrategyMeritId, ...] = ("s1", "s2", "s3", "s4", "s5", "s6")


def run_research_strategy_suite_and_persist(
    db: Session,
    symbols: list[str],
    eval_start: date,
    eval_end: date,
    *,
    leg_b: str,
    s7_train_end: date,
    s7_symbol: str | None = None,
    rolling_splits: int = 1,
    split_mode: SplitMode = "calendar",
    trading_calendar_symbols: list[str] | None = None,
    ack_s7_overfitting_risk: bool = False,
    no_persist: bool = False,
) -> dict[str, Any]:
    """Run eval-bundle-equivalent merit for S1–S6 and S7 search; persist each report when enabled.

    S7 uses ``s7_symbol`` (default: first symbol in ``symbols``). Features are built from OHLCV
    on **[eval_start, eval_end]**; the backtest uses the full ``price_data`` series for that symbol.
    """
    sym_norm = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
    if len(sym_norm) < 2:
        raise ValueError("suite requires at least two symbols (S6 leg B must differ from panel)")
    leg_bu = leg_b.strip().upper()
    if leg_bu not in sym_norm:
        raise ValueError("leg_b must be one of the suite symbols (S6 panel + leg B)")
    sym_s7 = (s7_symbol or sym_norm[0]).strip().upper()
    if sym_s7 not in sym_norm:
        raise ValueError("s7_symbol must be included in the suite symbol list")

    cal_override = trading_calendar_symbols
    rs = max(1, int(rolling_splits))
    merit_ids: dict[str, int | None] = {}

    for strat in _STRATEGIES_S1_S6:
        pair_b = leg_bu if strat == "s6" else None
        bundle = run_strategy_merit_bundle(
            db,
            strat,
            sym_norm,
            eval_start,
            eval_end,
            rolling_splits=rs,
            split_mode=split_mode,
            trading_calendar_symbols=cal_override,
            pair_leg_b=pair_b,
        )
        rid = try_persist_merit_report(db, bundle, skip=no_persist)
        merit_ids[strat] = rid
        if rid is not None:
            logger.info("Persisted %s merit bundle → daily_strategy_merit_runs id=%s", strat, rid)

    s7_block: dict[str, Any]
    if not ack_s7_overfitting_risk:
        merit_ids["s7"] = None
        s7_block = {
            "skipped": True,
            "reason": "ack_s7_overfitting_risk is False",
            "merit_run_id": None,
        }
        return {
            "kind": "research_strategy_suite_result",
            "eval_window": {"start": str(eval_start), "end": str(eval_end)},
            "symbols_requested": sym_norm,
            "merit_run_ids": merit_ids,
            "s7": s7_block,
        }

    repo = PriceDataRepository(db)
    rows_db = repo.list_for_stock(sym_s7)
    bars_all = bars_from_price_rows(rows_db)
    bars_win = [b for b in bars_all if eval_start <= b.d <= eval_end]
    w = get_settings().s7_vol_z_window
    feat = build_feature_rows_from_bars(bars_win, vol_z_window=w)
    s7_report = run_rule_search(
        bars=bars_all,
        feature_rows=feat,
        train_end=s7_train_end,
        ack_overfitting_risk=True,
        symbol=sym_s7,
    )

    s7_rid: int | None = None
    if s7_report.get("error"):
        s7_block = {
            "skipped": False,
            "error": s7_report.get("error"),
            "message": s7_report.get("message"),
            "merit_run_id": None,
            "report": s7_report,
        }
    else:
        s7_rid = try_persist_merit_report(db, s7_report, skip=no_persist)
        s7_block = {
            "skipped": False,
            "error": None,
            "merit_run_id": s7_rid,
            "report": s7_report,
        }
        if s7_rid is not None:
            logger.info("Persisted S7 rule discovery → daily_strategy_merit_runs id=%s", s7_rid)

    merit_ids["s7"] = s7_rid

    return {
        "kind": "research_strategy_suite_result",
        "eval_window": {"start": str(eval_start), "end": str(eval_end)},
        "symbols_requested": sym_norm,
        "s7_symbol": sym_s7,
        "s7_train_end": str(s7_train_end),
        "merit_run_ids": merit_ids,
        "s7": {k: v for k, v in s7_block.items() if k != "report"},
        "s7_report": s7_block.get("report"),
    }

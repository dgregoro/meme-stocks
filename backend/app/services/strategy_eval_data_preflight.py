"""Preflight checks and optional data fetch for daily-strategy CLI evaluation (spec 019)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.services.daily_frequency_strategy_research import (
    DailyStrategySymbolDataAssessment,
    StrategyMeritId,
    _parse_horizons_setting,
    assess_daily_strategy_symbol_data,
)
from backend.app.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

PreflightMode = Literal["check", "ensure"]


@dataclass
class StrategyEvalPreflightResult:
    """Aggregate preflight outcome for one daily-strategy run."""

    strategy: StrategyMeritId
    eval_start: date | None
    eval_end: date | None
    mode: PreflightMode
    all_ready: bool
    symbols: list[dict[str, Any]] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "strategy_eval_data_preflight",
            "strategy": self.strategy,
            "eval_window": {
                "start": str(self.eval_start) if self.eval_start else None,
                "end": str(self.eval_end) if self.eval_end else None,
            },
            "mode": self.mode,
            "all_ready": self.all_ready,
            "symbols": self.symbols,
            "actions_taken": self.actions_taken,
            "errors": self.errors,
        }


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    return list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))


def _backfill_date_range(eval_start: date | None, eval_end: date | None) -> tuple[date, date]:
    """Alpaca [start, end] inclusive for daily bars (calendar buffers from config)."""
    settings = get_settings()
    prior = max(1, int(settings.daily_strategy_ensure_data_prior_calendar_days))
    end_buf = max(1, int(settings.daily_strategy_ensure_data_end_buffer_calendar_days))
    horizons = _parse_horizons_setting(settings.daily_strategy_horizons)
    max_h = max(horizons) if horizons else 10
    end_extra = max(end_buf, max_h * 3)

    if eval_start is not None and eval_end is not None:
        start_d = eval_start - timedelta(days=prior)
        end_d = eval_end + timedelta(days=end_extra)
        return start_d, end_d

    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=prior), today + timedelta(days=end_extra)


def _assess_all(
    db: Session,
    symbols: list[str],
    strategy: StrategyMeritId,
    eval_start: date | None,
    eval_end: date | None,
) -> list[DailyStrategySymbolDataAssessment]:
    return [assess_daily_strategy_symbol_data(db, sym, strategy, eval_start, eval_end) for sym in symbols]


def run_strategy_eval_data_preflight(
    db: Session,
    symbols: list[str],
    strategy: StrategyMeritId,
    eval_start: date | None,
    eval_end: date | None,
    *,
    mode: PreflightMode = "check",
    all_stocks_ensure: bool = False,
) -> StrategyEvalPreflightResult:
    """Verify (and optionally fetch) prerequisites for S1–S4 daily-strategy evaluation.

    S3 additionally requires persisted VIX/VIX3M observations (``backfill vol-term`` / Yahoo).
    S4 uses OHLCV only (calendar flags are computed from bar dates).

    * ``mode="check"``: read-only; no Alpaca.
    * ``mode="ensure"``: create missing ``stocks`` rows, then Alpaca daily backfill for symbols
      that are not ready, then re-check. Uses :func:`backfill_price_data_from_alpaca` (same as
      ``backfill daily-prices``).

    With ``all_stocks_ensure`` and ``mode=ensure``, enforces
    ``daily_strategy_ensure_data_max_symbols`` to avoid accidental mass API use.
    """
    syms = _dedupe_symbols(symbols)
    actions: list[str] = []
    errors: list[str] = []
    settings = get_settings()
    cap = max(1, int(settings.daily_strategy_ensure_data_max_symbols))

    if mode == "ensure" and all_stocks_ensure and len(syms) > cap:
        errors.append(
            f"--ensure-data with --all-stocks exceeds cap ({len(syms)} > {cap}); "
            "pass explicit --symbols, raise DAILY_STRATEGY_ENSURE_DATA_MAX_SYMBOLS in config, "
            "or run `seed stocks` / `backfill daily-prices` separately."
        )
        return StrategyEvalPreflightResult(
            strategy=strategy,
            eval_start=eval_start,
            eval_end=eval_end,
            mode=mode,
            all_ready=False,
            symbols=[],
            actions_taken=actions,
            errors=errors,
        )

    if mode == "ensure":
        from backend.app.services.stock_seed_service import ensure_stock_rows_for_symbols

        seed_r = ensure_stock_rows_for_symbols(db, syms)
        if seed_r.get("created", 0) > 0:
            db.commit()
            actions.append(f"stock_rows_created={seed_r['created']}")

        if strategy == "s3":
            bf_start, bf_end = _backfill_date_range(eval_start, eval_end)
            extra = max(1, int(settings.s3_macro_backfill_calendar_buffer_days))
            macro_start = bf_start - timedelta(days=extra)
            try:
                from backend.app.services.vol_term_structure_service import backfill_vol_term_observations

                vr = backfill_vol_term_observations(db, macro_start, bf_end, replace_range=False)
                actions.append(
                    f"backfill_vol_term rows_upserted={vr.get('rows_upserted', 0)} " f"range={macro_start}..{bf_end}"
                )
                for err in vr.get("errors") or []:
                    errors.append(str(err))
                    logger.warning("preflight vol-term backfill: %s", err)
            except Exception as exc:
                msg = str(exc)
                errors.append(msg)
                logger.warning("preflight vol-term backfill failed: %s", exc)

    assessments = _assess_all(db, syms, strategy, eval_start, eval_end)
    all_ready = all(a.status == "ready" for a in assessments)

    if mode == "ensure" and not all_ready:
        need_fetch = [a.symbol for a in assessments if a.status != "ready"]
        bf_start, bf_end = _backfill_date_range(eval_start, eval_end)
        try:
            from backend.app.services.leader_follower_replay_service import (
                backfill_price_data_from_alpaca,
            )

            bf = backfill_price_data_from_alpaca(db, need_fetch, bf_start, bf_end)
            actions.append(
                f"backfill_price_data rows_inserted={bf.get('rows_inserted', 0)} "
                f"symbols_fetched={bf.get('symbols_fetched', 0)} range={bf_start}..{bf_end}"
            )
            for err in bf.get("errors") or []:
                errors.append(str(err))
                logger.warning("preflight backfill batch error: %s", err)
        except ExternalAPIError as exc:
            msg = str(exc)
            errors.append(msg)
            logger.warning("preflight backfill failed: %s", exc)

        assessments = _assess_all(db, syms, strategy, eval_start, eval_end)
        all_ready = all(a.status == "ready" for a in assessments)

    if all_ready:
        errors = []
    else:
        for a in assessments:
            if a.status != "ready":
                hint = a.message or a.status
                errors.append(f"{a.symbol}: {a.status} — {hint}")

    sym_payload = [
        {
            "symbol": a.symbol,
            "status": a.status,
            "message": a.message,
            "min_bars_required": a.min_bars_required,
            "valid_bar_count": a.valid_bar_count,
            "raw_price_row_count": a.raw_price_row_count,
        }
        for a in assessments
    ]

    return StrategyEvalPreflightResult(
        strategy=strategy,
        eval_start=eval_start,
        eval_end=eval_end,
        mode=mode,
        all_ready=all_ready,
        symbols=sym_payload,
        actions_taken=actions,
        errors=errors,
    )

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal, cast

import typer
from sqlalchemy.orm import Session

from backend.app.cli.common import load_symbols_from_path, parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def _emit_merit_report_stdout_jsonl(
    report: dict,
    *,
    splits: int,
    append_jsonl: str | None,
) -> None:
    """Stderr summary for rolling vs single merit; stdout JSON; optional JSONL append."""
    if splits > 1:
        nskip = sum(len(p["report"].get("symbols_skipped") or []) for p in report.get("splits", []))
        if nskip:
            typer.echo(f"Note: {nskip} total symbol skip entries across splits (see JSON).", err=True)
        rp = report.get("rollup", {})
        if rp.get("rolling_pass") is True:
            typer.echo("rolling rollup: PASS (splits checklist + excess sign stable)", err=True)
        else:
            typer.echo(
                "rolling rollup: FAIL — see rollup.instability_failures and per-split checklist",
                err=True,
            )
    else:
        if report.get("symbols_skipped"):
            typer.echo(
                f"Note: skipped {len(report['symbols_skipped'])} symbol(s); see JSON symbols_skipped.",
                err=True,
            )
        chk = report.get("checklist", {})
        if chk.get("pass") is True:
            typer.echo("checklist: PASS (automated minimum bar only)", err=True)
        else:
            typer.echo("checklist: FAIL — see checklist.failures in JSON", err=True)

    typer.echo(json.dumps(report, indent=2, default=str))
    if append_jsonl:
        path = Path(append_jsonl).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, default=str) + "\n")
        typer.echo(f"Appended JSONL line to {path}", err=True)


def _emit_strategy_merit_bundle_stdout_jsonl(
    bundle: dict,
    *,
    append_jsonl: str | None,
) -> None:
    """Stderr gate summary; stdout full bundle JSON; optional JSONL append."""
    summ = bundle.get("summary") or {}
    if summ.get("all_automated_gates_pass") is True:
        typer.echo("bundle gates: PASS (single-window checklist + rolling if configured)", err=True)
    else:
        gfs = summ.get("gate_failures") or []
        typer.echo(f"bundle gates: FAIL — {gfs} — see summary in JSON", err=True)
    rec = summ.get("recommendation")
    if rec:
        typer.echo(f"recommendation: {rec}", err=True)

    chk = bundle.get("single_window", {}).get("checklist", {})
    if chk.get("pass") is True:
        typer.echo("single-window checklist: PASS", err=True)
    else:
        typer.echo("single-window checklist: FAIL — see single_window.checklist.failures", err=True)

    roll = bundle.get("rolling")
    if roll is not None:
        rp = roll.get("rollup", {})
        if rp.get("rolling_pass") is True:
            typer.echo("rolling rollup: PASS", err=True)
        else:
            typer.echo("rolling rollup: FAIL — see rolling.rollup", err=True)

    nskip = len(bundle.get("single_window", {}).get("symbols_skipped") or [])
    if nskip:
        typer.echo(f"Note: single_window skipped {nskip} symbol(s); see symbols_skipped.", err=True)

    typer.echo(json.dumps(bundle, indent=2, default=str))
    if append_jsonl:
        path = Path(append_jsonl).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(bundle, default=str) + "\n")
        typer.echo(f"Appended JSONL line to {path}", err=True)


def _daily_strategy_preflight_phase(
    db: Session,
    sym_list: list[str],
    strategy: str,
    eval_start: date | None,
    eval_end: date | None,
    *,
    preflight_only: bool,
    ensure_data: bool,
    all_stocks: bool,
) -> None:
    """Run spec-019 preflight; exit on failure. ``preflight_only`` prints JSON and exits."""
    from backend.app.services.daily_frequency_strategy_research import StrategyMeritId
    from backend.app.services.strategy_eval_data_preflight import run_strategy_eval_data_preflight

    if preflight_only and ensure_data:
        typer.echo("Error: use either --preflight-only or --ensure-data, not both", err=True)
        raise typer.Exit(1)

    if not preflight_only and not ensure_data:
        return

    sid = cast(StrategyMeritId, strategy.strip().lower())
    mode: Literal["check", "ensure"] = "ensure" if ensure_data else "check"
    result = run_strategy_eval_data_preflight(
        db,
        sym_list,
        sid,
        eval_start,
        eval_end,
        mode=mode,
        all_stocks_ensure=bool(ensure_data and all_stocks),
    )

    if preflight_only:
        typer.echo(json.dumps(result.as_json_dict(), indent=2, default=str))
        raise typer.Exit(0 if result.all_ready else 2)

    if ensure_data:
        for line in result.actions_taken:
            typer.echo(f"preflight: {line}", err=True)
        if not result.all_ready:
            for err in result.errors:
                typer.echo(f"preflight: {err}", err=True)
            typer.echo(
                "preflight failed after --ensure-data (see messages above). Exit 2 = data still insufficient.",
                err=True,
            )
            raise typer.Exit(2)


def register_evaluate(app: typer.Typer) -> None:
    evaluate_app = typer.Typer(help="On-demand research evaluation summaries (read-only).")
    app.add_typer(evaluate_app, name="evaluate")

    daily_strat = typer.Typer(help="Daily OHLCV strategies (S1/S2); see docs/STRATEGY_TESTING_PLAN.md.")
    evaluate_app.add_typer(daily_strat, name="daily-strategy")

    @daily_strat.command("eval-bundle")
    def evaluate_daily_strategy_merit_bundle(
        strategy: str = typer.Option(
            ...,
            "--strategy",
            help="s1 (vol vs realized-vol mismatch) or s2 (gap ecology)",
        ),
        start: str = typer.Option(..., "--start", help="Eval window start (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", help="Eval window end (YYYY-MM-DD)"),
        symbols: str | None = typer.Option(
            None,
            "--symbols",
            help="Comma-separated tickers (omit if using --all-stocks or --symbols-file)",
        ),
        symbols_file: str | None = typer.Option(
            None,
            "--symbols-file",
            help="Path to tickers (one per line; from research universe sp1500-cap-filter --output-symbols-file)",
        ),
        all_stocks: bool = typer.Option(
            False,
            "--all-stocks",
            help="Use every symbol in the stocks table (needs price_data per symbol)",
        ),
        rolling_splits: int = typer.Option(
            5,
            "--rolling-splits",
            help="If >=2, add rolling merit + rollup on that many sub-windows; use 1 for single-window only",
            min=1,
            max=24,
        ),
        split_mode: str = typer.Option(
            "trading",
            "--split-mode",
            help="calendar or trading (default trading: union of --trading-calendar-symbols dates)",
        ),
        trading_calendar_symbols: str | None = typer.Option(
            None,
            "--trading-calendar-symbols",
            help="Comma tickers for trading-day union when --split-mode trading (default: eval symbols)",
        ),
        append_jsonl: str | None = typer.Option(
            None,
            "--append-jsonl",
            help="Append one JSON line (full bundle) to this path",
        ),
        preflight_only: bool = typer.Option(
            False,
            "--preflight-only",
            help="Only verify OHLCV prerequisites; print JSON; exit 2 if any symbol not ready (no network)",
        ),
        ensure_data: bool = typer.Option(
            False,
            "--ensure-data",
            help="Before eval: create missing stock rows and Alpaca backfill if needed (requires API keys)",
        ),
    ) -> None:
        """Automated strategy gate: pooled merit on [start,end] plus optional rolling stability (one JSON blob)."""
        from backend.app.data.repositories.stock_repo import StockRepository
        from backend.app.services.daily_frequency_strategy_research import (
            SplitMode,
            StrategyMeritId,
            run_strategy_merit_bundle,
        )

        strat = strategy.strip().lower()
        if strat not in ("s1", "s2"):
            typer.echo("Error: --strategy must be s1 or s2", err=True)
            raise typer.Exit(1)
        strategy_id = cast(StrategyMeritId, strat)

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
        sm = split_mode.strip().lower()
        if sm not in ("calendar", "trading"):
            typer.echo("Error: --split-mode must be calendar or trading", err=True)
            raise typer.Exit(1)
        split_mode_t = cast(SplitMode, sm)

        if start_d > end_d:
            typer.echo("Error: --start must be on or before --end", err=True)
            raise typer.Exit(1)
        if symbols and symbols_file:
            typer.echo("Error: pass either --symbols or --symbols-file, not both", err=True)
            raise typer.Exit(1)
        if all_stocks and (symbols or symbols_file):
            typer.echo(
                "Error: --all-stocks cannot be combined with --symbols or --symbols-file",
                err=True,
            )
            raise typer.Exit(1)
        if not all_stocks and not symbols and not symbols_file:
            typer.echo("Error: pass --symbols, --symbols-file, or --all-stocks", err=True)
            raise typer.Exit(1)

        init_db()
        db = SessionLocal()
        try:
            if all_stocks:
                sym_list = [s.symbol for s in StockRepository(db).list()]
            elif symbols_file is not None:
                sf = Path(symbols_file)
                if not sf.is_file():
                    typer.echo(f"Error: --symbols-file not found: {sf}", err=True)
                    raise typer.Exit(1)
                sym_list = load_symbols_from_path(sf)
                if not sym_list:
                    typer.echo("Error: --symbols-file is empty", err=True)
                    raise typer.Exit(1)
            else:
                if symbols is None:
                    typer.echo("Error: --symbols required unless --all-stocks or --symbols-file", err=True)
                    raise typer.Exit(1)
                sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            _daily_strategy_preflight_phase(
                db,
                sym_list,
                strat,
                start_d,
                end_d,
                preflight_only=preflight_only,
                ensure_data=ensure_data,
                all_stocks=all_stocks,
            )
            cal_override = None
            if trading_calendar_symbols:
                cal_override = [s.strip().upper() for s in trading_calendar_symbols.split(",") if s.strip()]

            bundle = run_strategy_merit_bundle(
                db,
                strategy_id,
                sym_list,
                start_d,
                end_d,
                rolling_splits=rolling_splits,
                split_mode=split_mode_t,
                trading_calendar_symbols=cal_override,
            )
            sk_bundle = bundle.get("single_window", {}).get("symbols_skipped") or []
            if sk_bundle and not ensure_data:
                typer.echo(
                    "Tip: use --preflight-only to inspect data readiness or --ensure-data to seed/backfill (Alpaca).",
                    err=True,
                )
            _emit_strategy_merit_bundle_stdout_jsonl(bundle, append_jsonl=append_jsonl)
        finally:
            db.close()

    @daily_strat.command("s1-merit")
    def evaluate_daily_s1_merit(
        start: str = typer.Option(..., "--start", help="Hold-out / eval window start (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", help="Eval window end (YYYY-MM-DD)"),
        symbols: str | None = typer.Option(
            None,
            "--symbols",
            help="Comma-separated tickers (omit if using --all-stocks or --symbols-file)",
        ),
        symbols_file: str | None = typer.Option(
            None,
            "--symbols-file",
            help="Path to tickers (one per line)",
        ),
        all_stocks: bool = typer.Option(
            False,
            "--all-stocks",
            help="Use every symbol in the stocks table (needs price_data per symbol)",
        ),
        splits: int = typer.Option(
            1,
            "--splits",
            help="If >1, run merit on contiguous calendar sub-windows and add excess sign-stability rollup",
            min=1,
            max=24,
        ),
        append_jsonl: str | None = typer.Option(
            None,
            "--append-jsonl",
            help="Append one JSON line to this path (e.g. data/research/s1_merit_runs.jsonl)",
        ),
        split_mode: str = typer.Option(
            "calendar",
            "--split-mode",
            help="calendar (default) or trading (union of price_data dates from --trading-calendar-symbols)",
        ),
        trading_calendar_symbols: str | None = typer.Option(
            None,
            "--trading-calendar-symbols",
            help="Comma tickers for trading-day union when --split-mode trading (default: same as --symbols / --all-stocks)",
        ),
        preflight_only: bool = typer.Option(
            False,
            "--preflight-only",
            help="Only verify OHLCV prerequisites; print JSON; exit 2 if any symbol not ready",
        ),
        ensure_data: bool = typer.Option(
            False,
            "--ensure-data",
            help="Before merit run: create missing stock rows and Alpaca backfill if needed",
        ),
    ) -> None:
        """Pooled S1 over [start,end]: baseline comparison + automated checklist (JSON)."""
        from backend.app.data.repositories.stock_repo import StockRepository
        from backend.app.services.daily_frequency_strategy_research import (
            SplitMode,
            run_s1_merit_report,
            run_s1_merit_rolling_report,
        )

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
        sm = split_mode.strip().lower()
        if sm not in ("calendar", "trading"):
            typer.echo("Error: --split-mode must be calendar or trading", err=True)
            raise typer.Exit(1)
        split_mode_t = cast(SplitMode, sm)

        if start_d > end_d:
            typer.echo("Error: --start must be on or before --end", err=True)
            raise typer.Exit(1)
        if symbols and symbols_file:
            typer.echo("Error: pass either --symbols or --symbols-file, not both", err=True)
            raise typer.Exit(1)
        if all_stocks and (symbols or symbols_file):
            typer.echo(
                "Error: --all-stocks cannot be combined with --symbols or --symbols-file",
                err=True,
            )
            raise typer.Exit(1)
        if not all_stocks and not symbols and not symbols_file:
            typer.echo("Error: pass --symbols, --symbols-file, or --all-stocks", err=True)
            raise typer.Exit(1)

        init_db()
        db = SessionLocal()
        try:
            if all_stocks:
                sym_list = [s.symbol for s in StockRepository(db).list()]
            elif symbols_file is not None:
                sf = Path(symbols_file)
                if not sf.is_file():
                    typer.echo(f"Error: --symbols-file not found: {sf}", err=True)
                    raise typer.Exit(1)
                sym_list = load_symbols_from_path(sf)
                if not sym_list:
                    typer.echo("Error: --symbols-file is empty", err=True)
                    raise typer.Exit(1)
            else:
                if symbols is None:
                    typer.echo("Error: --symbols required unless --all-stocks or --symbols-file", err=True)
                    raise typer.Exit(1)
                sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            cal_override = None
            if trading_calendar_symbols:
                cal_override = [s.strip().upper() for s in trading_calendar_symbols.split(",") if s.strip()]

            _daily_strategy_preflight_phase(
                db,
                sym_list,
                "s1",
                start_d,
                end_d,
                preflight_only=preflight_only,
                ensure_data=ensure_data,
                all_stocks=all_stocks,
            )

            if splits > 1:
                report = run_s1_merit_rolling_report(
                    db,
                    sym_list,
                    start_d,
                    end_d,
                    n_splits=splits,
                    split_mode=split_mode_t,
                    trading_calendar_symbols=cal_override,
                )
            else:
                report = run_s1_merit_report(db, sym_list, start_d, end_d)

            if report.get("symbols_skipped") and not ensure_data:
                typer.echo(
                    "Tip: use --preflight-only to inspect data readiness or --ensure-data to seed/backfill (Alpaca).",
                    err=True,
                )
            _emit_merit_report_stdout_jsonl(report, splits=splits, append_jsonl=append_jsonl)
        finally:
            db.close()

    @daily_strat.command("s2-merit")
    def evaluate_daily_s2_merit(
        start: str = typer.Option(..., "--start", help="Eval window start (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", help="Eval window end (YYYY-MM-DD)"),
        symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated tickers"),
        symbols_file: str | None = typer.Option(None, "--symbols-file", help="Path to tickers (one per line)"),
        all_stocks: bool = typer.Option(False, "--all-stocks", help="Use all symbols in stocks table"),
        splits: int = typer.Option(1, "--splits", min=1, max=24),
        append_jsonl: str | None = typer.Option(None, "--append-jsonl"),
        split_mode: str = typer.Option("calendar", "--split-mode"),
        trading_calendar_symbols: str | None = typer.Option(
            None,
            "--trading-calendar-symbols",
        ),
        preflight_only: bool = typer.Option(False, "--preflight-only"),
        ensure_data: bool = typer.Option(
            False,
            "--ensure-data",
            help="Before merit run: create missing stock rows and Alpaca backfill if needed",
        ),
    ) -> None:
        """Pooled S2 gap ecology: same automation pattern as s1-merit."""
        from backend.app.data.repositories.stock_repo import StockRepository
        from backend.app.services.daily_frequency_strategy_research import (
            SplitMode,
            run_s2_merit_report,
            run_s2_merit_rolling_report,
        )

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
        sm = split_mode.strip().lower()
        if sm not in ("calendar", "trading"):
            typer.echo("Error: --split-mode must be calendar or trading", err=True)
            raise typer.Exit(1)
        split_mode_t = cast(SplitMode, sm)

        if start_d > end_d:
            typer.echo("Error: --start must be on or before --end", err=True)
            raise typer.Exit(1)
        if symbols and symbols_file:
            typer.echo("Error: pass either --symbols or --symbols-file, not both", err=True)
            raise typer.Exit(1)
        if all_stocks and (symbols or symbols_file):
            typer.echo(
                "Error: --all-stocks cannot be combined with --symbols or --symbols-file",
                err=True,
            )
            raise typer.Exit(1)
        if not all_stocks and not symbols and not symbols_file:
            typer.echo("Error: pass --symbols, --symbols-file, or --all-stocks", err=True)
            raise typer.Exit(1)

        init_db()
        db = SessionLocal()
        try:
            if all_stocks:
                sym_list = [s.symbol for s in StockRepository(db).list()]
            elif symbols_file is not None:
                sf = Path(symbols_file)
                if not sf.is_file():
                    typer.echo(f"Error: --symbols-file not found: {sf}", err=True)
                    raise typer.Exit(1)
                sym_list = load_symbols_from_path(sf)
                if not sym_list:
                    typer.echo("Error: --symbols-file is empty", err=True)
                    raise typer.Exit(1)
            else:
                if symbols is None:
                    typer.echo("Error: --symbols required unless --all-stocks or --symbols-file", err=True)
                    raise typer.Exit(1)
                sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            cal_override = None
            if trading_calendar_symbols:
                cal_override = [s.strip().upper() for s in trading_calendar_symbols.split(",") if s.strip()]

            _daily_strategy_preflight_phase(
                db,
                sym_list,
                "s2",
                start_d,
                end_d,
                preflight_only=preflight_only,
                ensure_data=ensure_data,
                all_stocks=all_stocks,
            )

            if splits > 1:
                report = run_s2_merit_rolling_report(
                    db,
                    sym_list,
                    start_d,
                    end_d,
                    n_splits=splits,
                    split_mode=split_mode_t,
                    trading_calendar_symbols=cal_override,
                )
            else:
                report = run_s2_merit_report(db, sym_list, start_d, end_d)

            if report.get("symbols_skipped") and not ensure_data:
                typer.echo(
                    "Tip: use --preflight-only to inspect data readiness or --ensure-data to seed/backfill (Alpaca).",
                    err=True,
                )
            _emit_merit_report_stdout_jsonl(report, splits=splits, append_jsonl=append_jsonl)
        finally:
            db.close()

    @daily_strat.command("s1")
    def evaluate_daily_s1(
        symbol: str = typer.Option(..., "--symbol", "-s", help="Stock symbol"),
        start: str | None = typer.Option(None, "--start", help="Evaluate dates on/after (YYYY-MM-DD)"),
        end: str | None = typer.Option(None, "--end", help="Evaluate dates on/before (YYYY-MM-DD)"),
        preflight_only: bool = typer.Option(False, "--preflight-only"),
        ensure_data: bool = typer.Option(
            False,
            "--ensure-data",
            help="Before eval: create missing stock row and Alpaca backfill if needed",
        ),
    ) -> None:
        """S1: realized vol vs volume-z mismatch regimes; forward returns by horizon (JSON)."""
        from backend.app.services.daily_frequency_strategy_research import run_s1_evaluation

        start_d = parse_cli_date(start) if start else None
        end_d = parse_cli_date(end) if end else None
        init_db()
        db = SessionLocal()
        try:
            _daily_strategy_preflight_phase(
                db,
                [symbol.upper()],
                "s1",
                start_d,
                end_d,
                preflight_only=preflight_only,
                ensure_data=ensure_data,
                all_stocks=False,
            )
            summary = run_s1_evaluation(db, symbol.upper(), start_d, end_d)
            if summary.get("hint"):
                typer.echo(summary["hint"], err=True)
            typer.echo(json.dumps(summary, indent=2, default=str))
        finally:
            db.close()

    @daily_strat.command("s2")
    def evaluate_daily_s2(
        symbol: str = typer.Option(..., "--symbol", "-s", help="Stock symbol"),
        start: str | None = typer.Option(None, "--start", help="Evaluate dates on/after (YYYY-MM-DD)"),
        end: str | None = typer.Option(None, "--end", help="Evaluate dates on/before (YYYY-MM-DD)"),
        preflight_only: bool = typer.Option(False, "--preflight-only"),
        ensure_data: bool = typer.Option(
            False,
            "--ensure-data",
            help="Before eval: create missing stock row and Alpaca backfill if needed",
        ),
    ) -> None:
        """S2: gap ecology vs MA trend; forward returns from signal close (JSON)."""
        from backend.app.services.daily_frequency_strategy_research import run_s2_evaluation

        start_d = parse_cli_date(start) if start else None
        end_d = parse_cli_date(end) if end else None
        init_db()
        db = SessionLocal()
        try:
            _daily_strategy_preflight_phase(
                db,
                [symbol.upper()],
                "s2",
                start_d,
                end_d,
                preflight_only=preflight_only,
                ensure_data=ensure_data,
                all_stocks=False,
            )
            summary = run_s2_evaluation(db, symbol.upper(), start_d, end_d)
            if summary.get("hint"):
                typer.echo(summary["hint"], err=True)
            typer.echo(json.dumps(summary, indent=2, default=str))
        finally:
            db.close()

    @evaluate_app.command("volume-spike")
    def evaluate_volume_spike(
        start: str | None = typer.Option(None, "--start", "-s", help="Filter event_date >= (YYYY-MM-DD)"),
        end: str | None = typer.Option(None, "--end", "-e", help="Filter event_date <= (YYYY-MM-DD)"),
        symbol: str | None = typer.Option(None, "--symbol", help="Single symbol filter"),
        limit: int = typer.Option(
            500,
            "--limit",
            help="Max events to evaluate (cap 2000; raise for long windows)",
            min=1,
            max=2000,
        ),
    ) -> None:
        """Print JSON evaluation summary (forward returns by horizon and event_type)."""
        from backend.app.services.volume_spike_evaluation_service import (
            aggregate_volume_spike_summary,
            run_volume_spike_evaluation,
        )

        start_d = parse_cli_date(start) if start else None
        end_d = parse_cli_date(end) if end else None

        init_db()
        db = SessionLocal()
        try:
            events, price_by_symbol, horizons = run_volume_spike_evaluation(
                db, since_date=start_d, until_date=end_d, symbol=symbol, limit=limit
            )
            summary = aggregate_volume_spike_summary(events, price_by_symbol, horizons)
            typer.echo(json.dumps(summary, indent=2, default=str))
        finally:
            db.close()

    @evaluate_app.command("extreme-move")
    def evaluate_extreme_move(
        start: str | None = typer.Option(None, "--start", "-s", help="Filter event_date >= (YYYY-MM-DD)"),
        end: str | None = typer.Option(None, "--end", "-e", help="Filter event_date <= (YYYY-MM-DD)"),
        symbol: str | None = typer.Option(None, "--symbol", help="Single symbol filter"),
        limit: int = typer.Option(
            500,
            "--limit",
            help="Max events to evaluate (cap 2000; raise for long windows)",
            min=1,
            max=2000,
        ),
        group_by: str | None = typer.Option(
            None,
            "--group-by",
            help="Optional: magnitude | volume | magnitude_volume (017 context buckets)",
        ),
    ) -> None:
        """Print JSON evaluation summary (forward returns by horizon and event_type)."""
        from backend.app.services.extreme_move_evaluation_service import (
            aggregate_evaluation_by_magnitude,
            aggregate_evaluation_by_magnitude_volume,
            aggregate_evaluation_by_volume,
            aggregate_extreme_move_summary,
            run_extreme_move_evaluation,
        )

        allowed = ("magnitude", "volume", "magnitude_volume")
        if group_by is not None and group_by not in allowed:
            typer.echo(f"Error: --group-by must be one of {list(allowed)}", err=True)
            raise typer.Exit(1)

        start_d = parse_cli_date(start) if start else None
        end_d = parse_cli_date(end) if end else None

        init_db()
        db = SessionLocal()
        try:
            events, price_by_symbol, horizons = run_extreme_move_evaluation(
                db, since_date=start_d, until_date=end_d, symbol=symbol, limit=limit
            )
            if group_by is None:
                summary = aggregate_extreme_move_summary(events, price_by_symbol, horizons)
                typer.echo(json.dumps(summary, indent=2, default=str))
            elif group_by == "magnitude":
                typer.echo(
                    json.dumps(
                        aggregate_evaluation_by_magnitude(events, price_by_symbol, horizons),
                        indent=2,
                        default=str,
                    )
                )
            elif group_by == "volume":
                typer.echo(
                    json.dumps(
                        aggregate_evaluation_by_volume(events, price_by_symbol, horizons),
                        indent=2,
                        default=str,
                    )
                )
            else:
                typer.echo(
                    json.dumps(
                        aggregate_evaluation_by_magnitude_volume(events, price_by_symbol, horizons),
                        indent=2,
                        default=str,
                    )
                )
        finally:
            db.close()

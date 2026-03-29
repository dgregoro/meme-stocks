"""CLI for backend operations that use the database directly (e.g. build-dataset).

Invoke with: python -m backend.app.cli build-dataset --start 2026-01-01 --end 2026-02-28 --out /tmp/dataset.csv
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from subprocess import CalledProcessError  # nosec B404
from typing import Literal, cast

import typer

from backend.app.data.database import SessionLocal, init_db

# Import all models so init_db can create all tables (FK dependencies, migrations)
from backend.app.models import (  # noqa: F401
    intraday_ingest_run,
    intraday_ingest_state,
    job_execution,
    job_lock,
    job_run_history,
    leader_event,
    leader_follower_candidate,
    leader_follower_optimization_result,
    leader_follower_optimization_run,
    leader_follower_robustness_aggregate,
    leader_follower_robustness_run,
    leader_follower_robustness_split_result,
    leader_follower_paper_run,
    leader_follower_paper_trade,
    leader_follower_signal,
    notification,
    paper_trade,
    price_data,
    price_labels,
    reddit_daily_feature,
    reddit_post,
    reddit_symbol_mention,
    stock,
    stock_group,
    symbol_universe,
    volume_spike_event,
    extreme_move_event,
)
from backend.app.services.dataset_builder_service import build_training_dataset
from backend.app.services.experiments.directionality import run_directionality
from backend.app.services.experiments.event_study import run_event_study
from backend.app.services.experiments.predictiveness import run_predictiveness
from backend.app.services.label_service import compute_and_store_forward_returns

app = typer.Typer(
    name="meme-stocks-app",
    help="Backend app CLI for DB-backed operations (dataset builder).",
    no_args_is_help=True,
)

build_dataset_app = typer.Typer(invoke_without_command=True)
app.add_typer(build_dataset_app, name="build-dataset")

seed_app = typer.Typer(help="Bootstrap and seed data.")
app.add_typer(seed_app, name="seed")

experiment_app = typer.Typer(help="Run causal research experiments.")
app.add_typer(experiment_app, name="experiment")

backfill_app = typer.Typer(help="Historical backfill for leader-follower signals.")
app.add_typer(backfill_app, name="backfill")

simulate_app = typer.Typer(help="Simulate leader-follower paper trading from signals + price data.")
app.add_typer(simulate_app, name="simulate")

optimize_app = typer.Typer(help="Walk-forward optimization over paper-trading parameters (research).")
app.add_typer(optimize_app, name="optimize")

robustness_app = typer.Typer(help="Rolling walk-forward robustness evaluation (research).")
app.add_typer(robustness_app, name="robustness")

evaluate_app = typer.Typer(help="On-demand research evaluation summaries (read-only).")
app.add_typer(evaluate_app, name="evaluate")

research_app = typer.Typer(
    help="Orchestrate multi-step research pipelines from trusted YAML recipes (spec 018).",
)
app.add_typer(research_app, name="research")

recipe_app = typer.Typer(help="Load and run declarative research recipes.")
research_app.add_typer(recipe_app, name="recipe")


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


@build_dataset_app.callback(invoke_without_command=True)
def build_dataset(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    horizon: int = typer.Option(5, "--horizon", help="Forward-return horizon in days"),
    out: str = typer.Option(..., "--out", "-o", help="Output file path (CSV or .parquet)"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format: csv or parquet"),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols to include (default: all)"),
) -> None:
    """Build training dataset: compute forward-return labels and join with Reddit daily features.

    Writes a deterministic snapshot with no look-ahead. Features for trading_day D
    use only data available up to D; labels use close[D+horizon]/close[D]-1.
    """
    start_d = _parse_date(start)
    end_d = _parse_date(end)

    init_db()
    db = SessionLocal()
    try:
        # Populate labels for horizons 1, 5, 10 (per CAUSAL_RESEARCH.md)
        label_stats = compute_and_store_forward_returns(
            db,
            start_d,
            end_d,
            horizons=[1, 5, 10],
        )
        db.commit()

        symbol_list = [s.strip() for s in symbols.split(",")] if symbols else None
        fmt: Literal["csv", "parquet"] = "csv" if format.lower() == "csv" else "parquet"
        ds_stats = build_training_dataset(
            db,
            start_d,
            end_d,
            horizon_days=horizon,
            symbols=symbol_list,
            output_path=out,
            format=fmt,
        )
        typer.echo(f"Labels: {label_stats['rows_upserted']} rows (horizons 1/5/10)")
        typer.echo(f"Dataset: {ds_stats['rows_written']} rows written to {out}")
    finally:
        db.close()


@seed_app.command("stocks")
def seed_stocks() -> None:
    """Seed stocks table with symbols from BOOTSTRAP_GROUPS. Idempotent; run before stock-groups."""
    from backend.app.services.stock_seed_service import seed_stocks_for_bootstrap

    init_db()
    db = SessionLocal()
    try:
        result = seed_stocks_for_bootstrap(db)
        db.commit()
        typer.echo(f"Stocks seeded: {result['created']} created, {result['total'] - result['created']} already existed")
    finally:
        db.close()


@seed_app.command("stock-groups")
def seed_stock_groups() -> None:
    """Seed stock_groups with curated bootstrap data. Idempotent; run 'seed stocks' first."""
    from backend.app.services.stock_group_seed_service import run_bootstrap_seed

    init_db()
    db = SessionLocal()
    try:
        result = run_bootstrap_seed(db)
        db.commit()
        typer.echo(
            f"Stock groups seeded: {result['groups_inserted']} inserted, "
            f"{result['groups_skipped']} skipped (already existed)"
        )
        if result["stocks_created"] > 0:
            typer.echo(f"Created {result['stocks_created']} missing stocks for FK integrity")
        if result["symbols_skipped"]:
            typer.echo("Skipped (with warnings):")
            for s in result["symbols_skipped"]:
                typer.echo(f"  - {s}")
    finally:
        db.close()


@backfill_app.command("leader-follower")
def backfill_leader_follower(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Compute metrics only; do not persist signals"),
    replace_range: bool = typer.Option(
        False, "--replace-range", help="Delete existing signals in [start,end] before replay"
    ),
) -> None:
    """Replay leader-follower detection for a historical date range.

    Uses Alpaca daily bars to backfill PriceData, then runs detection per date.
    Requires: stock_groups seeded, Alpaca API keys configured.
    """
    from backend.app.utils.errors import ExternalAPIError

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        typer.echo("Error: start_date must be <= end_date", err=True)
        raise typer.Exit(1)

    init_db()
    db = SessionLocal()
    try:
        from backend.app.services.leader_follower_replay_service import run_backfill

        result = run_backfill(
            db,
            start_d,
            end_d,
            dry_run=dry_run,
            persist=not dry_run,
            replace_range=replace_range,
        )
        typer.echo(f"Backfill leader-follower: {start_d} to {end_d}")
        typer.echo(f"Days processed: {result['days_processed']}")
        typer.echo(f"Days skipped: {result['days_skipped']}")
        typer.echo(f"Leaders detected: {result['leaders_detected']}")
        typer.echo(f"Candidates found: {result['candidates_found']}")
        typer.echo(f"Signals emitted: {result['signals_emitted']}")
        typer.echo(f"Signals skipped (duplicate): {result['signals_skipped_duplicate']}")
        if result.get("missing_data_warnings"):
            typer.echo("Warnings: " + ", ".join(result["missing_data_warnings"]))
        if result.get("errors"):
            typer.echo("Errors: " + "; ".join(result["errors"][:5]))
            if len(result["errors"]) > 5:
                typer.echo(f"  ... and {len(result['errors']) - 5} more")
            raise typer.Exit(2)
    except ExternalAPIError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2)
    finally:
        db.close()


@backfill_app.command("daily-prices")
def backfill_daily_prices(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    symbols: str | None = typer.Option(
        None,
        "--symbols",
        help="Comma-separated tickers (default: all symbols in stocks table; run seed stocks first)",
    ),
) -> None:
    """Fetch Alpaca daily bars into price_data only (no leader-follower detection).

    Use this to populate the container DB before volume-spike / extreme-move backfills.
    Requires ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY.
    """
    from backend.app.services.leader_follower_replay_service import run_daily_price_backfill
    from backend.app.utils.errors import ExternalAPIError

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        typer.echo("Error: start_date must be <= end_date", err=True)
        raise typer.Exit(1)
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None

    init_db()
    db = SessionLocal()
    try:
        result = run_daily_price_backfill(db, start_d, end_d, symbols=sym_list)
        typer.echo(f"Backfill daily-prices: {start_d} to {end_d}")
        typer.echo(json.dumps(result, indent=2))
        if result.get("errors"):
            if any("no symbols" in err for err in result["errors"]):
                raise typer.Exit(1)
            raise typer.Exit(2)
    except ExternalAPIError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2)
    finally:
        db.close()


@backfill_app.command("volume-spike")
def backfill_volume_spike(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated tickers (default: all stocks in DB)"),
    replace_range: bool = typer.Option(
        False,
        "--replace-range",
        help="Delete existing volume_spike_events in [start,end] before insert",
    ),
) -> None:
    """Detect and persist volume spike events from daily price_data (research, 015)."""
    from backend.app.services.volume_spike_service import backfill_volume_spikes

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        typer.echo("Error: start_date must be <= end_date", err=True)
        raise typer.Exit(1)
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None

    init_db()
    db = SessionLocal()
    try:
        result = backfill_volume_spikes(db, start_d, end_d, symbols=sym_list, replace_range=replace_range)
        typer.echo(f"Backfill volume-spike: {start_d} to {end_d}")
        typer.echo(json.dumps(result, indent=2))
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

    start_d = _parse_date(start) if start else None
    end_d = _parse_date(end) if end else None

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


@backfill_app.command("extreme-move")
def backfill_extreme_move(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated tickers (default: all stocks in DB)"),
    replace_range: bool = typer.Option(
        False,
        "--replace-range",
        help="Delete existing extreme_move_events in [start,end] before insert",
    ),
) -> None:
    """Detect and persist extreme daily return events from price_data (research, 016)."""
    from backend.app.services.extreme_move_service import backfill_extreme_moves

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        typer.echo("Error: start_date must be <= end_date", err=True)
        raise typer.Exit(1)
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None

    init_db()
    db = SessionLocal()
    try:
        result = backfill_extreme_moves(db, start_d, end_d, symbols=sym_list, replace_range=replace_range)
        typer.echo(f"Backfill extreme-move: {start_d} to {end_d}")
        typer.echo(json.dumps(result, indent=2))
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

    start_d = _parse_date(start) if start else None
    end_d = _parse_date(end) if end else None

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


@simulate_app.command("leader-follower")
def simulate_leader_follower(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    entry: str = typer.Option("next_open", "--entry", help="next_open | same_close"),
    exit_mode: str = typer.Option("fixed_days", "--exit", help="fixed_days | early_exit"),
    holding_days: int = typer.Option(3, "--holding_days", help="Trading days to hold (fixed exit)"),
    max_positions_per_event: int = typer.Option(2, "--max_positions_per_event"),
    cost_pct: float = typer.Option(0.1, "--cost_pct", help="Round-trip cost in percentage points"),
    min_pair_score: float | None = typer.Option(None, "--min_pair_score"),
    sector_confirmation: bool = typer.Option(
        False,
        "--sector-confirmation/--no-sector-confirmation",
        help="Gate entries on sector ETF trend (013); default off",
    ),
    sector_trend_window: int = typer.Option(
        10,
        "--sector-trend-window",
        help="MA/window length for sector trend when confirmation is on",
    ),
    minimum_sector_return_pct: float = typer.Option(
        0.0,
        "--minimum-sector-return-pct",
        help="Extra sector return threshold (combined / rolling_return modes)",
    ),
    regime_filter: bool = typer.Option(
        False,
        "--regime-filter/--no-regime-filter",
        help="Gate entries on benchmark trend/vol (014); default off",
    ),
    regime_benchmark: str = typer.Option("SPY", "--regime-benchmark", help="Benchmark symbol for regime gate"),
    market_trend_window: int = typer.Option(20, "--market-trend-window", help="Days for benchmark MA"),
    require_market_uptrend: bool = typer.Option(
        True,
        "--require-market-uptrend/--no-require-market-uptrend",
        help="Require benchmark close > MA when regime filter on",
    ),
    volatility_window: int = typer.Option(10, "--volatility-window", help="Days for rolling return std"),
    volatility_threshold: float = typer.Option(
        0.02,
        "--volatility-threshold",
        help="Max allowed daily return std (decimal) when low-vol required",
    ),
    require_low_volatility: bool = typer.Option(
        False,
        "--require-low-volatility/--no-require-low-volatility",
        help="Require rolling vol <= threshold",
    ),
    regime_sector_strength: bool = typer.Option(
        False,
        "--regime-sector-strength/--no-regime-sector-strength",
        help="Also require sector confirmation pass (implies sector gate on)",
    ),
) -> None:
    """Run paper-trading simulation; persists a run and trades for API inspection."""
    from backend.app.services.leader_follower_paper_trading_service import (
        EntryMode,
        ExitMode,
        PaperTradingConfig,
        run_paper_trading_simulation,
    )

    if entry not in ("next_open", "same_close"):
        typer.echo("Error: --entry must be next_open or same_close", err=True)
        raise typer.Exit(1)
    if exit_mode not in ("fixed_days", "early_exit"):
        typer.echo("Error: --exit must be fixed_days or early_exit", err=True)
        raise typer.Exit(1)

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        typer.echo("Error: start_date must be <= end_date", err=True)
        raise typer.Exit(1)

    cfg = PaperTradingConfig(
        entry_mode=cast(EntryMode, entry),
        exit_mode=cast(ExitMode, exit_mode),
        holding_days=holding_days,
        max_positions_per_event=max_positions_per_event,
        min_pair_score=min_pair_score,
        per_trade_cost_pct=cost_pct,
        sector_confirmation_enabled=sector_confirmation,
        sector_trend_window=sector_trend_window,
        minimum_sector_return_pct=minimum_sector_return_pct,
        regime_filter_enabled=regime_filter,
        regime_benchmark_symbol=regime_benchmark.strip().upper(),
        market_trend_window=market_trend_window,
        require_market_uptrend=require_market_uptrend,
        volatility_window=volatility_window,
        volatility_threshold=volatility_threshold,
        require_low_volatility=require_low_volatility,
        regime_sector_strength_required=regime_sector_strength,
    )

    init_db()
    db = SessionLocal()
    try:
        run = run_paper_trading_simulation(db, start_d, end_d, cfg)
        typer.echo(f"Paper trading run id={run.id}")
        typer.echo(f"  trades={run.total_trades} skipped={run.skipped_count}")
        typer.echo(f"  skipped_sector_confirmation_count={run.skipped_sector_confirmation_count}")
        typer.echo(f"  skipped_regime_filter_count={run.skipped_regime_filter_count}")
        typer.echo(f"  cumulative_return_pct={run.cumulative_return_pct:.4f}")
        typer.echo(f"  max_drawdown_pct={run.max_drawdown_pct:.4f}")
        typer.echo(f"  win_rate={run.win_rate:.4f} avg_return_pct={run.avg_return_pct:.4f}")
    finally:
        db.close()


@optimize_app.command("leader-follower")
def optimize_leader_follower(
    train_start: str = typer.Option(..., "--train-start", help="Train window start (YYYY-MM-DD)"),
    train_end: str = typer.Option(..., "--train-end", help="Train window end (YYYY-MM-DD)"),
    validate_start: str = typer.Option(..., "--validate-start"),
    validate_end: str = typer.Option(..., "--validate-end"),
    test_start: str | None = typer.Option(None, "--test-start"),
    test_end: str | None = typer.Option(None, "--test-end"),
    grid_file: str | None = typer.Option(
        None,
        "--grid-file",
        help="JSON grid file (base_config, grid, ranking); default uses built-in small grid",
    ),
) -> None:
    """Run walk-forward grid search; persists optimization run + ranked results."""
    from backend.app.services.leader_follower_walk_forward_service import (
        DEFAULT_GRID_FILE_PAYLOAD,
        WalkForwardValidationError,
        read_optimization_grid_file,
        run_walk_forward_optimization,
    )

    train_s = _parse_date(train_start)
    train_e = _parse_date(train_end)
    val_s = _parse_date(validate_start)
    val_e = _parse_date(validate_end)
    test_s = _parse_date(test_start) if test_start else None
    test_e = _parse_date(test_end) if test_end else None

    grid_payload = copy.deepcopy(DEFAULT_GRID_FILE_PAYLOAD)
    if grid_file:
        try:
            grid_payload = read_optimization_grid_file(grid_file)
        except OSError as e:
            typer.echo(f"Error reading grid file: {e}", err=True)
            raise typer.Exit(1) from e

    init_db()
    db = SessionLocal()
    try:
        run = run_walk_forward_optimization(
            db,
            train_start=train_s,
            train_end=train_e,
            validate_start=val_s,
            validate_end=val_e,
            test_start=test_s,
            test_end=test_e,
            grid_payload=grid_payload,
        )
        typer.echo(f"Optimization run id={run.id} ranking={run.ranking_method}")
    except WalkForwardValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        db.close()


@robustness_app.command("leader-follower")
def robustness_leader_follower(
    overall_start: str = typer.Option(..., "--overall-start", help="Overall range start (YYYY-MM-DD)"),
    overall_end: str = typer.Option(..., "--overall-end", help="Overall range end (YYYY-MM-DD)"),
    train_window_months: int = typer.Option(..., "--train-window-months"),
    validate_window_months: int = typer.Option(..., "--validate-window-months"),
    step_months: int = typer.Option(..., "--step-months"),
    test_window_months: int | None = typer.Option(
        None,
        "--test-window-months",
        help="Optional forward test window length in calendar months",
    ),
    grid_file: str | None = typer.Option(None, "--grid-file", help="JSON grid file (base_config, grid, ranking)"),
    candidates_file: str | None = typer.Option(
        None, "--candidates-file", help="JSON file with base_config + candidates list + ranking"
    ),
) -> None:
    """Run rolling robustness across many splits; persists per-split rows and aggregate ranks."""
    from backend.app.services.leader_follower_rolling_robustness_service import (
        RollingRobustnessValidationError,
        read_rolling_robustness_file,
        run_rolling_robustness_evaluation,
    )

    if bool(grid_file) == bool(candidates_file):
        typer.echo("Error: provide exactly one of --grid-file or --candidates-file", err=True)
        raise typer.Exit(1)

    path: str = grid_file if grid_file else (candidates_file or "")
    if not path:
        typer.echo("Error: missing grid or candidates file path", err=True)
        raise typer.Exit(1)
    try:
        payload = read_rolling_robustness_file(path)
    except OSError as e:
        typer.echo(f"Error reading file: {e}", err=True)
        raise typer.Exit(1) from e
    except RollingRobustnessValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    o_s = _parse_date(overall_start)
    o_e = _parse_date(overall_end)
    if o_s > o_e:
        typer.echo("Error: overall_start must be <= overall_end", err=True)
        raise typer.Exit(1)
    if train_window_months < 1 or validate_window_months < 1 or step_months < 1:
        typer.echo("Error: train/validate/step window months must be >= 1", err=True)
        raise typer.Exit(1)
    if test_window_months is not None and test_window_months < 1:
        typer.echo("Error: test_window_months must be >= 1 when set", err=True)
        raise typer.Exit(1)

    init_db()
    db = SessionLocal()
    try:
        run = run_rolling_robustness_evaluation(
            db,
            overall_start=o_s,
            overall_end=o_e,
            train_months=train_window_months,
            validate_months=validate_window_months,
            test_months=test_window_months,
            step_months=step_months,
            source_payload=payload,
        )
        typer.echo(f"Robustness run id={run.id} splits={run.split_count} ranking={run.ranking_method}")
    except RollingRobustnessValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        db.close()


@experiment_app.command("directionality")
def experiment_directionality(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
    k: int = typer.Option(5, "--k", help="Number of lag periods"),
    h: int = typer.Option(1, "--h", help="Horizon for fwd_return and future mention lookahead"),
) -> None:
    """Directionality sanity check: mentions lead returns vs returns lead mentions."""
    result = run_directionality(dataset_path=dataset, k=k, h=h)
    typer.echo("Directionality results:")
    m_str = f"{result.mentions_lead_returns_corr:.4f}" if result.mentions_lead_returns_corr is not None else "N/A"
    r_str = f"{result.returns_lead_mentions_corr:.4f}" if result.returns_lead_mentions_corr is not None else "N/A"
    typer.echo(f"  mentions → returns: corr={m_str} (n={result.mentions_lead_returns_n})")
    typer.echo(f"  returns → mentions: corr={r_str} (n={result.returns_lead_mentions_n})")


@experiment_app.command("event-study")
def experiment_event_study(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
    window: int = typer.Option(20, "--window", "-w", help="Rolling window for spike definition"),
    threshold: str = typer.Option("p95", "--threshold", "-t", help="p95 for 95th percentile, or N for mean+N*std"),
    horizon: int = typer.Option(5, "--horizon", "-h", help="Forward-return horizon"),
) -> None:
    """Event study: average forward returns on mention spike vs non-spike days."""
    result = run_event_study(
        dataset_path=dataset,
        window=window,
        threshold=threshold,
        horizon=horizon,
    )
    typer.echo("Event study results:")
    sm = f"{result.spike_mean_fwd_return:.4f}" if result.spike_mean_fwd_return is not None else "N/A"
    nm = f"{result.non_spike_mean_fwd_return:.4f}" if result.non_spike_mean_fwd_return is not None else "N/A"
    sp = f"{result.spread:.4f}" if result.spread is not None else "N/A"
    typer.echo(f"  spike days:     mean_fwd_return={sm} (n={result.spike_n})")
    typer.echo(f"  non-spike days: mean_fwd_return={nm} (n={result.non_spike_n})")
    typer.echo(f"  spread (spike - non): {sp}")


@recipe_app.command("run")
def research_recipe_run(
    recipe_path: str = typer.Argument(..., help="Path to recipe YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print steps only; do not execute subprocesses"),
    cwd: str | None = typer.Option(
        None,
        "--cwd",
        help="Working directory for each step (default: current directory)",
    ),
) -> None:
    """Run a research recipe: each step invokes `python -m backend.app.cli <argv...>`."""
    from backend.app.services.research_recipe_runner import run_recipe_file

    path = Path(recipe_path)
    work = Path(cwd) if cwd else None
    try:
        summary = run_recipe_file(path, dry_run=dry_run, cwd=work)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except CalledProcessError as e:
        typer.echo(f"Recipe step failed with exit {e.returncode}", err=True)
        typer.echo(f"Command: {' '.join(str(x) for x in e.cmd)}", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(summary, indent=2, default=str))


@recipe_app.command("validate")
def research_recipe_validate(
    recipe_path: str = typer.Argument(..., help="Path to recipe YAML file"),
) -> None:
    """Parse and print the recipe as JSON (no subprocesses)."""
    from backend.app.services.research_recipe_runner import load_recipe_file, recipe_to_jsonable

    try:
        recipe = load_recipe_file(Path(recipe_path))
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(recipe_to_jsonable(recipe), indent=2, default=str))


@experiment_app.command("predictiveness")
def experiment_predictiveness(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
    horizon: int = typer.Option(5, "--horizon", "-h", help="Forward-return horizon"),
    split_date: str | None = typer.Option(
        None, "--split-date", "-s", help="Train/test split date (YYYY-MM-DD); default 80%%"
    ),
) -> None:
    """Predictiveness: baseline vs augmented (Reddit) out-of-sample metrics."""
    result = run_predictiveness(
        dataset_path=dataset,
        horizon=horizon,
        split_date=split_date,
    )
    typer.echo("Predictiveness results (time-based split):")
    typer.echo(f"  train n={result.n_train}  test n={result.n_test}")
    ba = f"{result.baseline_direction_accuracy:.4f}" if result.baseline_direction_accuracy is not None else "N/A"
    aa = f"{result.augmented_direction_accuracy:.4f}" if result.augmented_direction_accuracy is not None else "N/A"
    typer.echo(f"  direction accuracy: baseline={ba}  augmented={aa}")
    br = f"{result.baseline_ridge_rmse:.4f}" if result.baseline_ridge_rmse is not None else "N/A"
    ar = f"{result.augmented_ridge_rmse:.4f}" if result.augmented_ridge_rmse is not None else "N/A"
    typer.echo(f"  ridge RMSE:         baseline={br}  augmented={ar}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

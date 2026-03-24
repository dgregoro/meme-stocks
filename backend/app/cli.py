"""CLI for backend operations that use the database directly (e.g. build-dataset).

Invoke with: python -m backend.app.cli build-dataset --start 2026-01-01 --end 2026-02-28 --out /tmp/dataset.csv
"""

from __future__ import annotations

from datetime import date
from typing import Literal

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


@seed_app.command("stock-groups")
def seed_stock_groups() -> None:
    """Seed stock_groups with curated bootstrap data. Idempotent; safe to run twice."""
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

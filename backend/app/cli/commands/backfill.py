from __future__ import annotations

import json

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def register_backfill(app: typer.Typer) -> None:
    backfill_app = typer.Typer(help="Historical backfill for leader-follower signals.")
    app.add_typer(backfill_app, name="backfill")

    @backfill_app.command("leader-follower")
    def backfill_leader_follower(
        start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Compute metrics only; do not persist signals"),
        replace_range: bool = typer.Option(
            False, "--replace-range", help="Delete existing signals in [start,end] before replay"
        ),
    ) -> None:
        """Replay leader-follower detection for a historical date range."""
        from backend.app.utils.errors import ExternalAPIError

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
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
        """Fetch Alpaca daily bars into price_data only (no leader-follower detection)."""
        from backend.app.services.leader_follower_replay_service import run_daily_price_backfill
        from backend.app.utils.errors import ExternalAPIError

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
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
        symbols: str | None = typer.Option(
            None, "--symbols", help="Comma-separated tickers (default: all stocks in DB)"
        ),
        replace_range: bool = typer.Option(
            False,
            "--replace-range",
            help="Delete existing volume_spike_events in [start,end] before insert",
        ),
    ) -> None:
        """Detect and persist volume spike events from daily price_data (research, 015)."""
        from backend.app.services.volume_spike_service import backfill_volume_spikes

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
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

    @backfill_app.command("extreme-move")
    def backfill_extreme_move(
        start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
        symbols: str | None = typer.Option(
            None, "--symbols", help="Comma-separated tickers (default: all stocks in DB)"
        ),
        replace_range: bool = typer.Option(
            False,
            "--replace-range",
            help="Delete existing extreme_move_events in [start,end] before insert",
        ),
    ) -> None:
        """Detect and persist extreme daily return events from price_data (research, 016)."""
        from backend.app.services.extreme_move_service import backfill_extreme_moves

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
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

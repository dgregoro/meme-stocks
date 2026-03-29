from __future__ import annotations

import json

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def register_evaluate(app: typer.Typer) -> None:
    evaluate_app = typer.Typer(help="On-demand research evaluation summaries (read-only).")
    app.add_typer(evaluate_app, name="evaluate")

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

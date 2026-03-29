from __future__ import annotations

import copy

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def register_optimize(app: typer.Typer) -> None:
    optimize_app = typer.Typer(help="Walk-forward optimization over paper-trading parameters (research).")
    app.add_typer(optimize_app, name="optimize")

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

        train_s = parse_cli_date(train_start)
        train_e = parse_cli_date(train_end)
        val_s = parse_cli_date(validate_start)
        val_e = parse_cli_date(validate_end)
        test_s = parse_cli_date(test_start) if test_start else None
        test_e = parse_cli_date(test_end) if test_end else None

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

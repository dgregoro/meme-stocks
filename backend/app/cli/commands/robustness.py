from __future__ import annotations

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def register_robustness(app: typer.Typer) -> None:
    robustness_app = typer.Typer(help="Rolling walk-forward robustness evaluation (research).")
    app.add_typer(robustness_app, name="robustness")

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

        o_s = parse_cli_date(overall_start)
        o_e = parse_cli_date(overall_end)
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
            typer.echo(
                f"Robustness run id={run.id} splits={run.split_count} ranking={run.ranking_method}"
            )
        except RollingRobustnessValidationError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from e
        finally:
            db.close()
from __future__ import annotations

import json
from pathlib import Path
from subprocess import CalledProcessError  # nosec B404

import typer


def register_research(app: typer.Typer) -> None:
    research_app = typer.Typer(
        help="Orchestrate multi-step research pipelines from trusted YAML recipes (spec 018).",
    )
    app.add_typer(research_app, name="research")

    recipe_app = typer.Typer(help="Load and run declarative research recipes.")
    research_app.add_typer(recipe_app, name="recipe")

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

"""Assemble the Typer application for `python -m backend.app.cli`."""

from __future__ import annotations

import typer

import backend.app.cli.orm_imports  # noqa: F401
from backend.app.cli.commands.backfill import register_backfill
from backend.app.cli.commands.build_dataset import register_build_dataset
from backend.app.cli.commands.evaluate import register_evaluate
from backend.app.cli.commands.experiment import register_experiment
from backend.app.cli.commands.optimize import register_optimize
from backend.app.cli.commands.research import register_research
from backend.app.cli.commands.robustness import register_robustness
from backend.app.cli.commands.seed import register_seed
from backend.app.cli.commands.simulate import register_simulate

app = typer.Typer(
    name="meme-stocks-app",
    help="Backend app CLI for DB-backed operations (dataset builder, backfills, research).",
    no_args_is_help=True,
)

register_build_dataset(app)
register_seed(app)
register_experiment(app)
register_backfill(app)
register_simulate(app)
register_optimize(app)
register_robustness(app)
register_evaluate(app)
register_research(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""CLI for backend operations that use the database directly (e.g. build-dataset).

Invoke with: python -m backend.app.cli build-dataset --start 2026-01-01 --end 2026-02-28 --out /tmp/dataset.csv
"""

from __future__ import annotations

from datetime import date

import typer

from backend.app.data.database import SessionLocal, init_db

# Import all models so init_db can create all tables (FK dependencies)
from backend.app.models import (  # noqa: F401
    paper_trade,
    price_data,
    price_labels,
    reddit_daily_feature,
    reddit_post,
    reddit_symbol_mention,
    stock,
)
from backend.app.services.dataset_builder_service import build_training_dataset
from backend.app.services.label_service import compute_and_store_forward_returns

app = typer.Typer(
    name="meme-stocks-app",
    help="Backend app CLI for DB-backed operations (dataset builder).",
    no_args_is_help=True,
)

build_dataset_app = typer.Typer(invoke_without_command=True)
app.add_typer(build_dataset_app, name="build-dataset")


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


@build_dataset_app.callback(invoke_without_command=True)
def build_dataset(
    start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    horizon: int = typer.Option(5, "--horizon", help="Forward-return horizon in days"),
    out: str = typer.Option(..., "--out", "-o", help="Output file path (CSV or .parquet)"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format: csv or parquet"),
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
        label_stats = compute_and_store_forward_returns(
            db,
            start_d,
            end_d,
            horizons=[horizon],
        )
        db.commit()

        ds_stats = build_training_dataset(
            db,
            start_d,
            end_d,
            horizon_days=horizon,
            output_path=out,
            format=format,
        )
        typer.echo(f"Labels: {label_stats['rows_upserted']} rows for horizon {horizon}")
        typer.echo(f"Dataset: {ds_stats['rows_written']} rows written to {out}")
    finally:
        db.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()

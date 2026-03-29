from __future__ import annotations

from typing import Literal

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db
from backend.app.services.dataset_builder_service import build_training_dataset
from backend.app.services.label_service import compute_and_store_forward_returns


def register_build_dataset(app: typer.Typer) -> None:
    build_dataset_app = typer.Typer(invoke_without_command=True)
    app.add_typer(build_dataset_app, name="build-dataset")

    @build_dataset_app.callback(invoke_without_command=True)
    def build_dataset(
        start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
        horizon: int = typer.Option(5, "--horizon", help="Forward-return horizon in days"),
        out: str = typer.Option(..., "--out", "-o", help="Output file path (CSV or .parquet)"),
        format: str = typer.Option("csv", "--format", "-f", help="Output format: csv or parquet"),
        symbols: str | None = typer.Option(None, "--symbols", help="Comma-separated symbols to include (default: all)"),
    ) -> None:
        """Build training dataset: compute forward-return labels and join with Reddit daily features."""
        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)

        init_db()
        db = SessionLocal()
        try:
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

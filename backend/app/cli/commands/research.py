from __future__ import annotations

import json
from pathlib import Path
from subprocess import CalledProcessError  # nosec B404

import typer

from backend.app.cli.common import parse_cli_date


def register_research(app: typer.Typer) -> None:
    research_app = typer.Typer(
        help="Orchestrate multi-step research pipelines from trusted YAML recipes (spec 018).",
    )
    app.add_typer(research_app, name="research")

    universe_app = typer.Typer(
        help="Research equity universes (S&P Composite 1500 + cap filter; unofficial sources).",
    )
    research_app.add_typer(universe_app, name="universe")

    recipe_app = typer.Typer(help="Load and run declarative research recipes.")
    research_app.add_typer(recipe_app, name="recipe")

    rule_discovery_app = typer.Typer(
        help="S7 bounded rule discovery (hold-out quantile grid; high false-discovery risk). Not eval-bundle.",
    )
    research_app.add_typer(rule_discovery_app, name="rule-discovery")

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

    @universe_app.command("sp1500-fetch-wikipedia")
    def research_universe_sp1500_fetch_wikipedia(
        output: str = typer.Option(
            ...,
            "--output",
            "-o",
            help="Write merged tickers (one per line) to this path",
        ),
    ) -> None:
        """Fetch unofficial S&P 500+400+600 tickers from Wikipedia and save (not licensed index data)."""
        from backend.app.services.research_sp1500_universe_service import (
            fetch_sp_composite_1500_from_wikipedia,
        )
        from backend.app.utils.errors import ExternalAPIError

        try:
            syms = fetch_sp_composite_1500_from_wikipedia()
        except ExternalAPIError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(2)
        out = Path(output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(syms) + "\n", encoding="utf-8")
        typer.echo(f"Wrote {len(syms)} symbols to {out}", err=True)

    @universe_app.command("sp1500-cap-filter")
    def research_universe_sp1500_cap_filter(
        as_of: str = typer.Option(
            ...,
            "--as-of",
            help="Label for your snapshot (e.g. 2026-03-29); Yahoo caps are latest available, not backfilled",
        ),
        max_market_cap_usd: float = typer.Option(
            50e9,
            "--max-market-cap-usd",
            help="Keep symbols with Yahoo market cap strictly below this USD threshold",
        ),
        constituents_file: str | None = typer.Option(
            None,
            "--constituents-file",
            help="CSV or plain-text ticker list (defaults to research_sp1500_constituents_csv from config)",
        ),
        fetch_wikipedia: bool = typer.Option(
            False,
            "--fetch-wikipedia",
            help="Build constituent list from Wikipedia tables (writes no file; use fetch command to cache)",
        ),
        output_json: str | None = typer.Option(
            None,
            "--output-json",
            help="Write full result JSON to this path",
        ),
        output_symbols_file: str | None = typer.Option(
            None,
            "--output-symbols-file",
            help="Write included tickers one per line (for evaluate daily-strategy --symbols-file)",
        ),
        print_comma_symbols: bool = typer.Option(
            False,
            "--print-comma-symbols",
            help="Print included tickers as one comma-separated line (for evaluate --symbols)",
        ),
        seed_stocks: bool = typer.Option(
            False,
            "--seed-stocks",
            help="Create missing rows in stocks table for included symbols",
        ),
        throttle_sec: float = typer.Option(
            0.08,
            "--throttle-sec",
            help="Pause between Yahoo calls to reduce rate limiting",
            min=0.0,
        ),
    ) -> None:
        """Filter S&P Composite 1500 (or your CSV) by Yahoo market cap; exploratory / unofficial."""
        from backend.app.config import get_settings
        from backend.app.data.database import SessionLocal, init_db
        from backend.app.services.research_sp1500_universe_service import (
            fetch_sp_composite_1500_from_wikipedia,
            filter_sp1500_by_market_cap,
            load_constituents_csv,
        )
        from backend.app.services.stock_seed_service import ensure_stock_rows_for_symbols
        from backend.app.utils.errors import ExternalAPIError

        _ = parse_cli_date(as_of)

        if fetch_wikipedia and constituents_file:
            typer.echo("Error: pass either --fetch-wikipedia or --constituents-file, not both", err=True)
            raise typer.Exit(1)

        try:
            if fetch_wikipedia:
                symbols = fetch_sp_composite_1500_from_wikipedia()
                src = "wikipedia_live_fetch"
            else:
                path = Path(constituents_file if constituents_file else get_settings().research_sp1500_constituents_csv)
                if not path.is_file():
                    typer.echo(
                        f"Error: missing constituents file {path}. "
                        f"Run `research universe sp1500-fetch-wikipedia -o ...` or pass --constituents-file",
                        err=True,
                    )
                    raise typer.Exit(1)
                symbols = load_constituents_csv(path)
                src = str(path.resolve())
        except ExternalAPIError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(2)

        if not symbols:
            typer.echo("Error: no symbols loaded", err=True)
            raise typer.Exit(1)

        result = filter_sp1500_by_market_cap(
            symbols,
            max_market_cap_usd=max_market_cap_usd,
            as_of_label=as_of,
            constituents_source=src,
            throttle_sec=throttle_sec,
        )

        if seed_stocks:
            init_db()
            db = SessionLocal()
            try:
                ensure_stock_rows_for_symbols(db, result.included)
                db.commit()
                typer.echo(f"Seeded stocks table for {len(result.included)} symbol(s)", err=True)
            finally:
                db.close()

        payload = result.to_jsonable()
        if output_json:
            outp = Path(output_json).resolve()
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            typer.echo(f"Wrote JSON to {outp}", err=True)

        if output_symbols_file:
            symp = Path(output_symbols_file).resolve()
            symp.parent.mkdir(parents=True, exist_ok=True)
            symp.write_text("\n".join(result.included) + "\n", encoding="utf-8")
            typer.echo(f"Wrote {len(result.included)} symbol(s) to {symp}", err=True)

        typer.echo(json.dumps(payload, indent=2, default=str))
        if print_comma_symbols:
            typer.echo(",".join(result.included), err=True)

        if result.errors:
            typer.echo(f"Warning: {len(result.errors)} error(s) during cap lookup; see JSON", err=True)

    @rule_discovery_app.command("build-matrix")
    def research_rule_discovery_build_matrix(
        symbol: str = typer.Option(..., "--symbol", "-s", help="Ticker"),
        start: str = typer.Option(..., "--start", help="YYYY-MM-DD (inclusive)"),
        end: str = typer.Option(..., "--end", help="YYYY-MM-DD (inclusive)"),
        horizon: int = typer.Option(..., "--horizon", "-h", help="Forward return horizon (trading days)", min=1),
        output: str = typer.Option(..., "--output", "-o", help="Write CSV here"),
    ) -> None:
        """Build deterministic S7 daily feature + forward-label CSV from price_data (read-only)."""
        from backend.app.data.database import SessionLocal, init_db
        from backend.app.services.s7_rule_discovery.feature_matrix import (
            build_feature_matrix_rows,
            write_matrix_csv,
        )

        typer.echo(
            "S7 matrix: exploratory only; rolling features use same windows as S1-style settings.",
            err=True,
        )
        init_db()
        db = SessionLocal()
        try:
            s_d = parse_cli_date(start)
            e_d = parse_cli_date(end)
            rows, label = build_feature_matrix_rows(db, symbol, s_d, e_d, horizon)
            outp = Path(output).resolve()
            write_matrix_csv(outp, rows, label)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        finally:
            db.close()
        typer.echo(f"Wrote {len(rows)} rows label={label} -> {outp}", err=True)

    @rule_discovery_app.command("run-search")
    def research_rule_discovery_run_search(
        matrix_path: str = typer.Option(..., "--matrix", "-m", help="CSV from build-matrix"),
        train_end: str = typer.Option(..., "--train-end", help="Last inclusive train date YYYY-MM-DD"),
        ack_overfitting_risk: bool = typer.Option(
            False,
            "--ack-overfitting-risk",
            help="Required opt-in: acknowledges multiple-testing / overfitting hazard",
        ),
        label: str | None = typer.Option(
            None,
            "--label",
            help="Label column (default: infer single fwd_*_pct from CSV)",
        ),
        output: str | None = typer.Option(None, "--output", "-o", help="Write JSON here (stdout if omitted)"),
    ) -> None:
        """Run pre-registered quantile grid; requires --ack-overfitting-risk."""
        from backend.app.services.s7_rule_discovery.grid_search import run_search_from_matrix_path

        if not ack_overfitting_risk:
            typer.echo(
                "Error: refuse to run without --ack-overfitting-risk (S7 is exploratory; see spec 025).",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(
            "S7 search: results are not merit gates; treat as hypothesis generation only.",
            err=True,
        )
        path = Path(matrix_path).resolve()
        te = parse_cli_date(train_end)
        try:
            payload = run_search_from_matrix_path(path, train_end=te, label_key=label, ack_overfitting_risk=True)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        text = json.dumps(payload, indent=2, default=str)
        if output:
            outp = Path(output).resolve()
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(text, encoding="utf-8")
            typer.echo(f"Wrote JSON -> {outp}", err=True)
        typer.echo(text)

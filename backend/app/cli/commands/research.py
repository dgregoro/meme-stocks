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

    lf_research_app = typer.Typer(
        help="Near-miss / leader-debug statistics from persisted replay or scheduled runs.",
    )
    research_app.add_typer(lf_research_app, name="leader-follower")

    @lf_research_app.command("near-miss-upgrade")
    def research_leader_follower_near_miss_upgrade(
        start: str = typer.Option(..., "--start", "-s", help="Inclusive window start (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", "-e", help="Inclusive window end (YYYY-MM-DD)"),
        horizon: int = typer.Option(
            5,
            "--horizon",
            "-h",
            help="Forward trading sessions (per symbol price_data calendar); must be 1..252",
        ),
    ) -> None:
        """Share of near-miss symbol-days with a qualified leader event within H sessions (JSON)."""
        from backend.app.data.database import SessionLocal, init_db
        from backend.app.services.near_miss_leader_analysis_service import run_near_miss_upgrade_analysis
        from backend.app.utils.errors import DataAccessError

        since_d = parse_cli_date(start)
        until_d = parse_cli_date(end)
        if since_d > until_d:
            typer.echo("Error: --start must be <= --end", err=True)
            raise typer.Exit(1)

        init_db()
        db = SessionLocal()
        try:
            try:
                out = run_near_miss_upgrade_analysis(
                    db,
                    since_date=since_d,
                    until_date=until_d,
                    horizon_sessions=horizon,
                )
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1) from e
            except DataAccessError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(2) from e
            typer.echo(json.dumps(out, indent=2))
        finally:
            db.close()

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

    rule_discovery_app = typer.Typer(
        help="S7 — rule discovery on daily features (strict hold-out; requires --ack-overfitting-risk to search).",
    )
    research_app.add_typer(rule_discovery_app, name="rule-discovery")

    @rule_discovery_app.command("build-matrix")
    def research_rule_discovery_build_matrix(
        symbol: str = typer.Option(..., "--symbol", "-s", help="Ticker"),
        start: str = typer.Option(..., "--start", help="First calendar date (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", help="Last calendar date (YYYY-MM-DD)"),
        output: str = typer.Option(
            ...,
            "--output",
            "-o",
            help="Write CSV feature matrix (sidecar .meta.json next to it)",
        ),
    ) -> None:
        """Build deterministic S7 daily feature matrix from DB OHLCV (spec 025)."""
        from backend.app.config import get_settings
        from backend.app.data.database import SessionLocal, init_db
        from backend.app.data.repositories.price_data_repo import PriceDataRepository
        from backend.app.services.daily_frequency_strategy_research import bars_from_price_rows
        from backend.app.services.s7_rule_discovery import (
            build_feature_rows_from_bars,
            write_feature_matrix_csv,
        )

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
        if start_d > end_d:
            typer.echo("Error: --start must be on or before --end", err=True)
            raise typer.Exit(1)

        sym = symbol.strip().upper()
        init_db()
        db = SessionLocal()
        try:
            rows_db = PriceDataRepository(db).list_for_stock(sym)
            bars_all = bars_from_price_rows(rows_db)
            bars = [b for b in bars_all if start_d <= b.d <= end_d]
            if len(bars) < get_settings().s7_vol_z_window + 10:
                typer.echo(
                    f"Error: insufficient bars for {sym} in [{start_d}, {end_d}] "
                    f"({len(bars)} rows; widen range or backfill)",
                    err=True,
                )
                raise typer.Exit(2)
            w = get_settings().s7_vol_z_window
            feat = build_feature_rows_from_bars(bars, vol_z_window=w)
            if not feat:
                typer.echo("Error: no feature rows (check data quality / vol window)", err=True)
                raise typer.Exit(2)
            outp = write_feature_matrix_csv(
                output,
                feat,
                symbol=sym,
                meta_extra={"cli_start": str(start_d), "cli_end": str(end_d)},
            )
            typer.echo(json.dumps({"wrote": str(outp), "n_rows": len(feat)}, indent=2, default=str))
        finally:
            db.close()

    @rule_discovery_app.command("run-search")
    def research_rule_discovery_run_search(
        matrix: str = typer.Option(
            ...,
            "--matrix",
            "-m",
            help="Feature matrix CSV from build-matrix (expects sidecar .meta.json for symbol)",
        ),
        train_end: str = typer.Option(
            ...,
            "--train-end",
            help="Last train date inclusive (YYYY-MM-DD); rows after this are hold-out for reporting",
        ),
        symbol: str | None = typer.Option(
            None,
            "--symbol",
            "-s",
            help="Override symbol if .meta.json is missing",
        ),
        ack_overfitting_risk: bool = typer.Option(
            False,
            "--ack-overfitting-risk",
            help="Required acknowledgement: search has high false-discovery risk; no warranty of edge",
        ),
        no_persist: bool = typer.Option(
            False,
            "--no-persist",
            help="Do not store this run in daily_strategy_merit_runs",
        ),
    ) -> None:
        """Enumerate a bounded rule space on train quantiles; score hold-out trades (JSON)."""
        from backend.app.config import get_settings
        from backend.app.data.database import SessionLocal, init_db
        from backend.app.data.repositories.price_data_repo import PriceDataRepository
        from backend.app.services.daily_frequency_strategy_research import bars_from_price_rows
        from backend.app.services.daily_strategy_merit_persistence import try_persist_merit_report
        from backend.app.services.s7_rule_discovery import read_feature_matrix_csv, run_rule_search

        if not ack_overfitting_risk:
            typer.echo(
                "Error: refuse to run without --ack-overfitting-risk "
                "(S7 has high multiple-testing / overfitting hazard).",
                err=True,
            )
            raise typer.Exit(1)

        path = Path(matrix)
        train_end_d = parse_cli_date(train_end)
        feat_rows, meta = read_feature_matrix_csv(path)
        sym = (symbol or meta.get("symbol") or "").strip().upper()
        if not sym:
            typer.echo(
                'Error: missing symbol (pass --symbol or ensure .meta.json next to matrix has "symbol")',
                err=True,
            )
            raise typer.Exit(1)

        init_db()
        db = SessionLocal()
        try:
            rows_db = PriceDataRepository(db).list_for_stock(sym)
            bars = bars_from_price_rows(rows_db)
            if len(bars) < get_settings().s7_vol_z_window + 5:
                typer.echo(f"Error: insufficient price history in DB for {sym}", err=True)
                raise typer.Exit(2)
            out = run_rule_search(
                bars=bars,
                feature_rows=feat_rows,
                train_end=train_end_d,
                ack_overfitting_risk=True,
                symbol=sym,
            )
            if out.get("error"):
                typer.echo(json.dumps(out, indent=2, default=str))
                raise typer.Exit(2)
            rid = try_persist_merit_report(db, out, skip=no_persist)
            if rid is not None:
                typer.echo(
                    f"Recorded S7 run id={rid} (daily_strategy_merit_runs). "
                    f"Show: python -m backend.app.cli strategies merit-runs show --id {rid}",
                    err=True,
                )
            typer.echo(json.dumps(out, indent=2, default=str))
        finally:
            db.close()

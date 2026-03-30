"""Research strategy catalog CLI (S1–S7; optional evidence status file)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from backend.app.config import get_settings
from backend.app.data.database import SessionLocal, init_db
from backend.app.data.repositories.daily_strategy_merit_run_repo import DailyStrategyMeritRunRepository
from backend.app.services.strategy_catalog import (
    StrategyEvidenceFileError,
    build_strategy_list_rows,
    load_evidence_overrides,
    rows_to_json_serializable,
)


def register_strategies(app: typer.Typer) -> None:
    strat = typer.Typer(
        help="List daily-frequency research strategies (S1–S7) and optional evidence status.",
    )
    app.add_typer(strat, name="strategies")

    merit_runs = typer.Typer(help="Inspect persisted evaluate daily-strategy merit / bundle runs.")
    strat.add_typer(merit_runs, name="merit-runs")

    @merit_runs.command("list")
    def merit_runs_list(
        *,
        limit: int = typer.Option(50, "--limit", min=1, max=500, help="Max rows (newest first)"),
        json_out: bool = typer.Option(False, "--json", help="JSON array of index rows (no full report)"),
    ) -> None:
        """List recorded merit / eval-bundle runs (newest first)."""
        init_db()
        db = SessionLocal()
        try:
            rows = DailyStrategyMeritRunRepository(db).list_recent(limit=limit)
            if json_out:
                payload = [
                    {
                        "id": r.id,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "report_kind": r.report_kind,
                        "strategy_id": r.strategy_id,
                        "eval_start": str(r.eval_start),
                        "eval_end": str(r.eval_end),
                        "n_splits": r.n_splits,
                        "split_mode": r.split_mode,
                        "symbol_count": r.symbol_count,
                        "checklist_pass": r.checklist_pass,
                        "rolling_pass": r.rolling_pass,
                        "all_gates_pass": r.all_gates_pass,
                    }
                    for r in rows
                ]
                typer.echo(json.dumps(payload, indent=2))
                return
            for r in rows:
                typer.echo(
                    f"{r.id}\t{r.created_at.isoformat() if r.created_at else ''}\t"
                    f"{r.report_kind}\t{r.strategy_id}\t{r.eval_start}..{r.eval_end}\t"
                    f"sym={r.symbol_count}\tchk={r.checklist_pass}\troll={r.rolling_pass}\tgates={r.all_gates_pass}"
                )
        finally:
            db.close()

    @merit_runs.command("show")
    def merit_runs_show(
        run_id: int = typer.Option(..., "--id", help="Row id from merit-runs list"),
    ) -> None:
        """Print the full stored JSON report for one run (stdout)."""
        init_db()
        db = SessionLocal()
        try:
            row = DailyStrategyMeritRunRepository(db).get(run_id)
            if row is None:
                typer.echo(f"Error: no merit run with id={run_id}", err=True)
                raise typer.Exit(1)
            try:
                payload = json.loads(row.report_json)
                typer.echo(json.dumps(payload, indent=2, default=str))
            except json.JSONDecodeError:
                typer.echo(row.report_json)
        finally:
            db.close()

    @strat.command("list")
    def strategies_list(
        *,
        json_out: bool = typer.Option(False, "--json", help="Emit one JSON array (stdout only)"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Include descriptions and CLI hints"),
        status_file: str | None = typer.Option(
            None,
            "--status-file",
            help=(
                "Override RESEARCH_STRATEGY_EVIDENCE_STATUS_JSON " "(JSON map of S1..S7 to evidence fields; optional)"
            ),
        ),
    ) -> None:
        """Print strategy ID, name, tooling level, and evidence status.

        Evidence defaults: ``not_tested`` for strategies with CLI evaluation (S1–S2),
        ``n_a`` for roadmap-only (S3–S7). Override by creating the JSON file from
        ``data/research/strategy_evidence_status.example.json`` or via ``--status-file``.
        """
        settings = get_settings()
        path = Path(status_file).expanduser() if status_file else Path(settings.research_strategy_evidence_status_json)
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            overrides = load_evidence_overrides(path)
        except StrategyEvidenceFileError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from exc
        rows = build_strategy_list_rows(overrides)
        if json_out:
            typer.echo(json.dumps(rows_to_json_serializable(rows), indent=2))
            return
        for r in rows:
            extra = ""
            if r.verdict:
                extra += f" verdict={r.verdict}"
            if r.last_run_date:
                extra += f" last_run={r.last_run_date}"
            typer.echo(
                f"{r.strategy_id}\t{r.tooling}\t{r.evidence}\t{r.name}{extra}",
            )
            if verbose:
                typer.echo(f"    {r.description}")
                typer.echo(f"    data: {r.primary_data}")
                if r.cli_hint:
                    typer.echo(f"    cli: python -m backend.app.cli {r.cli_hint}")
                if r.notes:
                    typer.echo(f"    notes: {r.notes}")
                typer.echo("")

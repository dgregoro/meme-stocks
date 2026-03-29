from __future__ import annotations

import typer

from backend.app.services.experiments.directionality import run_directionality
from backend.app.services.experiments.event_study import run_event_study
from backend.app.services.experiments.predictiveness import run_predictiveness


def register_experiment(app: typer.Typer) -> None:
    experiment_app = typer.Typer(help="Run causal research experiments.")
    app.add_typer(experiment_app, name="experiment")

    @experiment_app.command("directionality")
    def experiment_directionality(
        dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
        k: int = typer.Option(5, "--k", help="Number of lag periods"),
        h: int = typer.Option(1, "--h", help="Horizon for fwd_return and future mention lookahead"),
    ) -> None:
        """Directionality sanity check: mentions lead returns vs returns lead mentions."""
        result = run_directionality(dataset_path=dataset, k=k, h=h)
        typer.echo("Directionality results:")
        m_str = (
            f"{result.mentions_lead_returns_corr:.4f}"
            if result.mentions_lead_returns_corr is not None
            else "N/A"
        )
        r_str = (
            f"{result.returns_lead_mentions_corr:.4f}"
            if result.returns_lead_mentions_corr is not None
            else "N/A"
        )
        typer.echo(f"  mentions → returns: corr={m_str} (n={result.mentions_lead_returns_n})")
        typer.echo(f"  returns → mentions: corr={r_str} (n={result.returns_lead_mentions_n})")

    @experiment_app.command("event-study")
    def experiment_event_study(
        dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
        window: int = typer.Option(20, "--window", "-w", help="Rolling window for spike definition"),
        threshold: str = typer.Option("p95", "--threshold", "-t", help="p95 for 95th percentile, or N for mean+N*std"),
        horizon: int = typer.Option(5, "--horizon", "-h", help="Forward-return horizon"),
    ) -> None:
        """Event study: average forward returns on mention spike vs non-spike days."""
        result = run_event_study(
            dataset_path=dataset,
            window=window,
            threshold=threshold,
            horizon=horizon,
        )
        typer.echo("Event study results:")
        sm = f"{result.spike_mean_fwd_return:.4f}" if result.spike_mean_fwd_return is not None else "N/A"
        nm = f"{result.non_spike_mean_fwd_return:.4f}" if result.non_spike_mean_fwd_return is not None else "N/A"
        sp = f"{result.spread:.4f}" if result.spread is not None else "N/A"
        typer.echo(f"  spike days:     mean_fwd_return={sm} (n={result.spike_n})")
        typer.echo(f"  non-spike days: mean_fwd_return={nm} (n={result.non_spike_n})")
        typer.echo(f"  spread (spike - non): {sp}")

    @experiment_app.command("predictiveness")
    def experiment_predictiveness(
        dataset: str = typer.Option(..., "--dataset", "-d", help="Path to CSV dataset"),
        horizon: int = typer.Option(5, "--horizon", "-h", help="Forward-return horizon"),
        split_date: str | None = typer.Option(
            None, "--split-date", "-s", help="Train/test split date (YYYY-MM-DD); default 80%%"
        ),
    ) -> None:
        """Predictiveness: baseline vs augmented (Reddit) out-of-sample metrics."""
        result = run_predictiveness(
            dataset_path=dataset,
            horizon=horizon,
            split_date=split_date,
        )
        typer.echo("Predictiveness results (time-based split):")
        typer.echo(f"  train n={result.n_train}  test n={result.n_test}")
        ba = f"{result.baseline_direction_accuracy:.4f}" if result.baseline_direction_accuracy is not None else "N/A"
        aa = f"{result.augmented_direction_accuracy:.4f}" if result.augmented_direction_accuracy is not None else "N/A"
        typer.echo(f"  direction accuracy: baseline={ba}  augmented={aa}")
        br = f"{result.baseline_ridge_rmse:.4f}" if result.baseline_ridge_rmse is not None else "N/A"
        ar = f"{result.augmented_ridge_rmse:.4f}" if result.augmented_ridge_rmse is not None else "N/A"
        typer.echo(f"  ridge RMSE:         baseline={br}  augmented={ar}")

from __future__ import annotations

from typing import cast

import typer

from backend.app.cli.common import parse_cli_date
from backend.app.data.database import SessionLocal, init_db


def register_simulate(app: typer.Typer) -> None:
    simulate_app = typer.Typer(help="Simulate leader-follower paper trading from signals + price data.")
    app.add_typer(simulate_app, name="simulate")

    @simulate_app.command("leader-follower")
    def simulate_leader_follower(
        start: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
        end: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
        entry: str = typer.Option("next_open", "--entry", help="next_open | same_close"),
        exit_mode: str = typer.Option("fixed_days", "--exit", help="fixed_days | early_exit"),
        holding_days: int = typer.Option(3, "--holding_days", help="Trading days to hold (fixed exit)"),
        max_positions_per_event: int = typer.Option(2, "--max_positions_per_event"),
        cost_pct: float = typer.Option(0.1, "--cost_pct", help="Round-trip cost in percentage points"),
        min_pair_score: float | None = typer.Option(None, "--min_pair_score"),
        sector_confirmation: bool = typer.Option(
            False,
            "--sector-confirmation/--no-sector-confirmation",
            help="Gate entries on sector ETF trend (013); default off",
        ),
        sector_trend_window: int = typer.Option(
            10,
            "--sector-trend-window",
            help="MA/window length for sector trend when confirmation is on",
        ),
        minimum_sector_return_pct: float = typer.Option(
            0.0,
            "--minimum-sector-return-pct",
            help="Extra sector return threshold (combined / rolling_return modes)",
        ),
        regime_filter: bool = typer.Option(
            False,
            "--regime-filter/--no-regime-filter",
            help="Gate entries on benchmark trend/vol (014); default off",
        ),
        regime_benchmark: str = typer.Option("SPY", "--regime-benchmark", help="Benchmark symbol for regime gate"),
        market_trend_window: int = typer.Option(20, "--market-trend-window", help="Days for benchmark MA"),
        require_market_uptrend: bool = typer.Option(
            True,
            "--require-market-uptrend/--no-require-market-uptrend",
            help="Require benchmark close > MA when regime filter on",
        ),
        volatility_window: int = typer.Option(10, "--volatility-window", help="Days for rolling return std"),
        volatility_threshold: float = typer.Option(
            0.02,
            "--volatility-threshold",
            help="Max allowed daily return std (decimal) when low-vol required",
        ),
        require_low_volatility: bool = typer.Option(
            False,
            "--require-low-volatility/--no-require-low-volatility",
            help="Require rolling vol <= threshold",
        ),
        regime_sector_strength: bool = typer.Option(
            False,
            "--regime-sector-strength/--no-regime-sector-strength",
            help="Also require sector confirmation pass (implies sector gate on)",
        ),
    ) -> None:
        """Run paper-trading simulation; persists a run and trades for API inspection."""
        from backend.app.services.leader_follower_paper_trading_service import (
            EntryMode,
            ExitMode,
            PaperTradingConfig,
            run_paper_trading_simulation,
        )

        if entry not in ("next_open", "same_close"):
            typer.echo("Error: --entry must be next_open or same_close", err=True)
            raise typer.Exit(1)
        if exit_mode not in ("fixed_days", "early_exit"):
            typer.echo("Error: --exit must be fixed_days or early_exit", err=True)
            raise typer.Exit(1)

        start_d = parse_cli_date(start)
        end_d = parse_cli_date(end)
        if start_d > end_d:
            typer.echo("Error: start_date must be <= end_date", err=True)
            raise typer.Exit(1)

        cfg = PaperTradingConfig(
            entry_mode=cast(EntryMode, entry),
            exit_mode=cast(ExitMode, exit_mode),
            holding_days=holding_days,
            max_positions_per_event=max_positions_per_event,
            min_pair_score=min_pair_score,
            per_trade_cost_pct=cost_pct,
            sector_confirmation_enabled=sector_confirmation,
            sector_trend_window=sector_trend_window,
            minimum_sector_return_pct=minimum_sector_return_pct,
            regime_filter_enabled=regime_filter,
            regime_benchmark_symbol=regime_benchmark.strip().upper(),
            market_trend_window=market_trend_window,
            require_market_uptrend=require_market_uptrend,
            volatility_window=volatility_window,
            volatility_threshold=volatility_threshold,
            require_low_volatility=require_low_volatility,
            regime_sector_strength_required=regime_sector_strength,
        )

        init_db()
        db = SessionLocal()
        try:
            run = run_paper_trading_simulation(db, start_d, end_d, cfg)
            typer.echo(f"Paper trading run id={run.id}")
            typer.echo(f"  trades={run.total_trades} skipped={run.skipped_count}")
            typer.echo(f"  skipped_sector_confirmation_count={run.skipped_sector_confirmation_count}")
            typer.echo(f"  skipped_regime_filter_count={run.skipped_regime_filter_count}")
            typer.echo(f"  cumulative_return_pct={run.cumulative_return_pct:.4f}")
            typer.echo(f"  max_drawdown_pct={run.max_drawdown_pct:.4f}")
            typer.echo(f"  win_rate={run.win_rate:.4f} avg_return_pct={run.avg_return_pct:.4f}")
        finally:
            db.close()

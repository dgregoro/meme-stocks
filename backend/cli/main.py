"""CLI entry point. Invoke with: python -m backend.cli.main or meme-stocks."""

from __future__ import annotations

import typer

from backend.cli import commands

app = typer.Typer(
    name="meme-stocks",
    help="Meme Stocks Trading Application CLI. Requires a running backend.",
    no_args_is_help=True,
)


# Global options (env vars: MEME_STOCKS_API_URL, MEME_STOCKS_OUTPUT)
base_url_opt = typer.Option(
    "http://127.0.0.1:8000",
    "--base-url",
    "-u",
    envvar="MEME_STOCKS_API_URL",
    help="Backend API base URL",
)
output_opt = typer.Option(
    "table",
    "--output",
    "-o",
    envvar="MEME_STOCKS_OUTPUT",
    help="Output format: table or json",
)


# --- Top-level commands ---


@app.command()
def health(
    base_url: str = base_url_opt,
) -> None:
    """Check backend connectivity."""
    commands.health_cmd(base_url=base_url)


@app.command()
def analysis(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Daily ranked analysis summary."""
    commands.analysis_cmd(base_url=base_url, output_fmt=output)


@app.command()
def portfolio(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Portfolio summary (paper trading)."""
    commands.portfolio_cmd(base_url=base_url, output_fmt=output)


@app.command()
def notifications(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """List unread notifications."""
    commands.notifications_cmd(base_url=base_url, output_fmt=output)


@app.command()
def sentiment(
    symbol: str = typer.Argument(..., help="Stock symbol (e.g. GME)"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Daily analysis fields for a symbol (keyword sentiment is unused without a social feed)."""
    commands.sentiment_cmd(symbol=symbol.upper(), base_url=base_url, output_fmt=output)


@app.command()
def prices(
    symbol: str = typer.Argument(..., help="Stock symbol (e.g. GME)"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Price history for a symbol."""
    commands.prices_cmd(symbol=symbol.upper(), base_url=base_url, output_fmt=output)


# --- Resource subcommands ---

stocks_app = typer.Typer(help="Stock management")
app.add_typer(stocks_app, name="stocks")


@stocks_app.command("list")
def stocks_list(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """List all tracked stocks."""
    commands.stocks_list_cmd(base_url=base_url, output_fmt=output)


@stocks_app.command("show")
def stocks_show(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Show stock details."""
    commands.stocks_show_cmd(symbol=symbol.upper(), base_url=base_url, output_fmt=output)


@stocks_app.command("mentions")
def stocks_mentions(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max mentions to show"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Recent Reddit mentions for a symbol (source: subreddit, url)."""
    commands.stocks_mentions_cmd(
        symbol=symbol.upper(),
        limit=limit,
        base_url=base_url,
        output_fmt=output,
    )


@stocks_app.command("add")
def stocks_add(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    name: str = typer.Option(None, "--name", "-n", help="Display name"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Add a stock to tracking."""
    commands.stocks_add_cmd(symbol=symbol.upper(), name=name or symbol, base_url=base_url, output_fmt=output)


trades_app = typer.Typer(help="Paper trading")
app.add_typer(trades_app, name="trades")


@trades_app.command("list")
def trades_list(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """List paper trades."""
    commands.trades_list_cmd(base_url=base_url, output_fmt=output)


@trades_app.command("create")
def trades_create(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    action: str = typer.Argument(..., help="buy or sell"),
    quantity: int = typer.Argument(..., help="Shares or contracts"),
    price: float = typer.Argument(..., help="Price per share or premium"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Create a paper trade."""
    commands.trades_create_cmd(
        symbol=symbol.upper(),
        action=action,
        quantity=quantity,
        price=price,
        base_url=base_url,
        output_fmt=output,
    )


@trades_app.command("close")
def trades_close(
    trade_id: int = typer.Argument(..., help="Trade ID to close"),
    exit_price: float = typer.Argument(..., help="Exit price"),
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Close a paper trade."""
    commands.trades_close_cmd(trade_id=trade_id, exit_price=exit_price, base_url=base_url, output=output)


symbols_app = typer.Typer(help="Symbol universe")
app.add_typer(symbols_app, name="symbols")


@symbols_app.command("refresh")
def symbols_refresh(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Refresh symbol universe from SEC/NASDAQ."""
    commands.symbols_refresh_cmd(base_url=base_url, output_fmt=output)


@symbols_app.command("stats")
def symbols_stats(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Symbol universe statistics."""
    commands.symbols_stats_cmd(base_url=base_url, output_fmt=output)


jobs_app = typer.Typer(help="Background jobs")
app.add_typer(jobs_app, name="jobs")


@jobs_app.command("prices")
def jobs_prices(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Trigger price collection."""
    commands.jobs_prices_cmd(base_url=base_url, output=output)


@jobs_app.command("notifications")
def jobs_notifications(
    base_url: str = base_url_opt,
    output: str = output_opt,
) -> None:
    """Trigger notification check."""
    commands.jobs_notifications_cmd(base_url=base_url, output=output)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

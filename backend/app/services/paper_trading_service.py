"""Paper trading: create/close trades, compute portfolio summary and win-rate metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.data.repositories.paper_trade_repo import PaperTradeRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.paper_trade import PaperTrade
from backend.app.utils.errors import DataAccessError


@dataclass(frozen=True)
class PortfolioSummary:
    """Aggregate view of paper trading positions and performance.

    Attributes:
        total_positions: Total number of trades (open + closed).
        open_positions: Trades not yet closed (no exit_price).
        closed_positions: Trades that have been closed.
        realized_pl: Sum of P/L from closed trades.
        unrealized_pl: Estimated P/L from open positions (requires current_prices).
        win_rate: Fraction of closed trades that are profitable (0-1), None if no closed trades.
        average_win: Mean P/L of winning trades in $, None if no wins.
        average_loss: Mean P/L of losing trades in $ (negative), None if no losses.
    """

    total_positions: int
    open_positions: int
    closed_positions: int
    realized_pl: float
    unrealized_pl: float
    win_rate: float | None  # 0-1, None when no closed trades
    average_win: float | None  # Avg $ per winning trade, None when no wins
    average_loss: float | None  # Avg $ per losing trade (negative), None when no losses


def create_trade(
    db: Session,
    *,
    symbol: str,
    action: str,
    quantity: int,
    price: float,
    notes: str | None = None,
) -> PaperTrade:
    """Create a paper trade (buy or sell). Symbol must exist in stocks table.

    Caller must commit the session after this returns.

    Raises:
        ValueError: If quantity/price <= 0 or action not in ('buy', 'sell').
        DataAccessError: If symbol is not a known stock.
    """
    if quantity <= 0 or price <= 0:
        raise ValueError("quantity and price must be positive")
    if action not in {"buy", "sell"}:
        raise ValueError("action must be 'buy' or 'sell'")
    if StockRepository(db).get(symbol) is None:
        raise DataAccessError("Unknown stock symbol")

    trade = PaperTrade(
        stock_symbol=symbol,
        action=action,
        quantity=quantity,
        entry_price=price,
        notes=notes,
    )
    PaperTradeRepository(db).add(trade)
    return trade


def close_trade(db: Session, trade_id: int, *, exit_price: float) -> PaperTrade:
    if exit_price <= 0:
        raise ValueError("exit_price must be positive")
    repo = PaperTradeRepository(db)
    trade = repo.get(trade_id)
    if trade is None:
        raise DataAccessError("Trade not found")
    trade.exit_price = exit_price
    trade.exit_at = datetime.now(timezone.utc)
    return trade


def compute_portfolio_summary(db: Session, *, current_prices: dict[str, float] | None = None) -> PortfolioSummary:
    """Compute portfolio stats from all paper trades.

    Realized P/L is computed from closed trades. Unrealized P/L uses
    current_prices when provided; otherwise 0. Win rate and avg win/loss
    are derived from closed-trade P/Ls.
    """
    repo = PaperTradeRepository(db)
    trades = repo.list()
    realized = 0.0
    unrealized = 0.0
    open_pos = 0
    closed_pos = 0
    pl_per_trade: list[float] = []

    for t in trades:
        direction = 1 if t.action == "buy" else -1
        if t.exit_price is not None:
            pl = direction * (t.exit_price - t.entry_price) * t.quantity
            realized += pl
            closed_pos += 1
            pl_per_trade.append(pl)
        else:
            open_pos += 1
            if current_prices and t.stock_symbol in current_prices:
                current = current_prices[t.stock_symbol]
                unrealized += direction * (current - t.entry_price) * t.quantity

    win_rate, average_win, average_loss = _compute_win_rate_metrics(pl_per_trade)

    return PortfolioSummary(
        total_positions=len(trades),
        open_positions=open_pos,
        closed_positions=closed_pos,
        realized_pl=round(realized, 2),
        unrealized_pl=round(unrealized, 2),
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
    )


def _compute_win_rate_metrics(
    pl_per_trade: list[float],
) -> tuple[float | None, float | None, float | None]:
    """Compute win rate, average win, average loss from closed-trade P/Ls.

    Returns:
        (win_rate, average_win, average_loss)
        win_rate: 0-1, None if no closed trades
        average_win: avg $ of winning trades, None if no wins
        average_loss: avg $ of losing trades (negative), None if no losses
    """
    if not pl_per_trade:
        return (None, None, None)
    wins = [p for p in pl_per_trade if p > 0]
    losses = [p for p in pl_per_trade if p < 0]
    win_rate = len(wins) / len(pl_per_trade)
    average_win = round(sum(wins) / len(wins), 2) if wins else None
    average_loss = round(sum(losses) / len(losses), 2) if losses else None
    return (round(win_rate, 4), average_win, average_loss)

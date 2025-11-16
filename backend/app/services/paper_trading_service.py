from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from backend.app.data.repositories.paper_trade_repo import PaperTradeRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.paper_trade import PaperTrade
from backend.app.utils.errors import DataAccessError


@dataclass(frozen=True)
class PortfolioSummary:
    total_positions: int
    open_positions: int
    closed_positions: int
    realized_pl: float
    unrealized_pl: float


def create_trade(
    db: Session, *, symbol: str, action: str, quantity: int, price: float, notes: str | None = None
) -> PaperTrade:
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
    repo = PaperTradeRepository(db)
    trades = repo.list()
    realized = 0.0
    unrealized = 0.0
    open_pos = 0
    closed_pos = 0

    for t in trades:
        direction = 1 if t.action == "buy" else -1
        if t.exit_price is not None:
            realized += direction * (t.exit_price - t.entry_price) * t.quantity
            closed_pos += 1
        else:
            open_pos += 1
            if current_prices and t.stock_symbol in current_prices:
                current = current_prices[t.stock_symbol]
                unrealized += direction * (current - t.entry_price) * t.quantity

    return PortfolioSummary(
        total_positions=len(trades),
        open_positions=open_pos,
        closed_positions=closed_pos,
        realized_pl=round(realized, 2),
        unrealized_pl=round(unrealized, 2),
    )



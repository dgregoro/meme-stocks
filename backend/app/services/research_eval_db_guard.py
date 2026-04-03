"""Ensure research evaluation does not run against an uninitialized OHLCV database."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock


class ResearchEvalDatabaseEmptyError(RuntimeError):
    """Raised when ``stocks`` or ``price_data`` has no rows (fresh / wiped DB)."""

    def __init__(self, message: str, *, stock_count: int, price_row_count: int) -> None:
        super().__init__(message)
        self.stock_count = stock_count
        self.price_row_count = price_row_count


def require_research_eval_db_has_prices(session: Session) -> None:
    """Fail fast if the database has no research universe or no OHLCV rows.

    Call at the start of strategy / event evaluation entrypoints so CLI and API
    never return plausible-looking JSON from an empty DB (PRD reliability).
    """
    stock_count = int(session.scalar(select(func.count()).select_from(Stock)) or 0)
    price_row_count = int(session.scalar(select(func.count()).select_from(PriceData)) or 0)
    if stock_count == 0 or price_row_count == 0:
        raise ResearchEvalDatabaseEmptyError(
            "Cannot run research evaluation: database has no stocks and/or no price_data rows. "
            "Seed symbols and backfill daily prices first "
            "(e.g. `python -m backend.app.cli seed stocks` and "
            "`python -m backend.app.cli backfill daily-prices --start … --end …`).",
            stock_count=stock_count,
            price_row_count=price_row_count,
        )

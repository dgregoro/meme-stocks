"""Bootstrap seeding for the stocks table.

Creates minimal Stock rows for symbols in BOOTSTRAP_GROUPS so that
stock_groups seed (and leader-follower backfill) can run successfully.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.data.stock_group_seed import BOOTSTRAP_GROUPS
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.stock import Stock


def seed_stocks_for_bootstrap(db: Session) -> dict[str, int]:
    """Create Stock rows for all symbols in BOOTSTRAP_GROUPS. Idempotent.

    Skips symbols that already exist. Returns created count.
    """
    all_symbols = set()
    for symbols in BOOTSTRAP_GROUPS.values():
        all_symbols.update(symbols)

    repo = StockRepository(db)
    created = 0
    for symbol in sorted(all_symbols):
        if repo.get(symbol) is None:
            repo.add(Stock(symbol=symbol, name=symbol, sector=None, market_cap=None))
            created += 1

    return {"created": created, "total": len(all_symbols)}

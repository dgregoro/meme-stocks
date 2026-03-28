"""Bootstrap seeding for stock groups.

Idempotent: running twice does not create duplicates. Skips symbols not present
in the stocks table (logs warning, does not create). Skips symbols that cannot
be added (e.g. constraint violation) and logs a warning.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy.orm import Session

from backend.app.data.stock_group_seed import BOOTSTRAP_GROUPS
from backend.app.data.repositories.stock_group_repo import StockGroupRepository
from backend.app.data.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class SeedResult(TypedDict):
    """Result of bootstrap seeding."""

    groups_inserted: int
    groups_skipped: int
    stocks_created: int  # Always 0; kept for CLI compatibility
    symbols_skipped: list[str]


def run_bootstrap_seed(db: Session) -> SeedResult:
    """Seed stock_groups with bootstrap data. Idempotent; does not wipe existing groups.

    For each (group_id, symbol) in BOOTSTRAP_GROUPS:
    - Skips symbol if not present in stocks table (logs warning)
    - Adds stock-group membership only if not already present

    Returns stats: groups_inserted, groups_skipped, stocks_created (0), symbols_skipped.
    """
    stock_repo = StockRepository(db)
    group_repo = StockGroupRepository(db)

    result: SeedResult = {
        "groups_inserted": 0,
        "groups_skipped": 0,
        "stocks_created": 0,
        "symbols_skipped": [],
    }

    for group_id, symbols in BOOTSTRAP_GROUPS.items():
        for symbol in symbols:
            try:
                if stock_repo.get(symbol) is None:
                    logger.warning("Skipped %s in group %s: symbol not in stocks table", symbol, group_id)
                    result["symbols_skipped"].append(f"{group_id}:{symbol} (not in stocks)")
                    continue

                if group_repo.add_if_missing(group_id, symbol):
                    result["groups_inserted"] += 1
                else:
                    result["groups_skipped"] += 1
            except Exception as exc:
                logger.warning(
                    "Skipped %s in group %s: %s",
                    symbol,
                    group_id,
                    exc,
                )
                result["symbols_skipped"].append(f"{group_id}:{symbol} ({exc})")

    return result

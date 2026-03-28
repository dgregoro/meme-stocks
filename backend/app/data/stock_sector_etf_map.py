"""Static stock symbol → sector ETF mapping for leader-follower sector confirmation (013)."""

from __future__ import annotations

# Uppercase symbols. Extend via PR; no DB migration required.
STOCK_TO_SECTOR_ETF: dict[str, str] = {
    "NVDA": "SMH",
    "AMD": "SMH",
    "INTC": "SMH",
    "AAPL": "XLK",
    "MSFT": "XLK",
    "TSLA": "XLY",
}


def resolve_sector_etf(leader_symbol: str, override: str | None) -> str | None:
    """Return ETF ticker for sector confirmation, or None if unmapped and no override."""
    if override:
        stripped = override.strip().upper()
        return stripped if stripped else None
    key = leader_symbol.strip().upper()
    return STOCK_TO_SECTOR_ETF.get(key)

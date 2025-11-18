from __future__ import annotations

import logging
import re
from typing import Set

logger = logging.getLogger(__name__)

# Common stock ticker pattern: 1-5 uppercase letters, possibly with $ prefix
# This is a simple regex; can be enhanced with a whitelist of valid tickers
TICKER_PATTERN = re.compile(r"\$?([A-Z]{1,5})\b")

# Common words that match ticker pattern but aren't stocks
# Filter these out to reduce false positives
COMMON_WORDS = {
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN",
    "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE",
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS",
    "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "ITS", "MAY",
    "NEW", "NOW", "OLD", "SEE", "TWO", "WHO", "WAY", "USE", "MAN", "YEAR", "HER",
    "SHE", "HIM", "HIS", "ITS", "THEY", "THEM", "THIS", "THAT", "THESE", "THOSE",
    "MOON", "MOONS", "BUY", "SELL", "HOLD", "DD", "YOLO", "WSB", "ETF", "IPO",
}

# Cache for symbol universe to avoid repeated DB queries
_symbol_universe_cache: Set[str] | None = None


def load_symbol_universe_from_db() -> Set[str]:
    """Load symbol universe from database (cached).

    Returns:
        Set of valid stock symbols, or empty set if unavailable.
    """
    global _symbol_universe_cache

    # Return cached value if available
    if _symbol_universe_cache is not None:
        return _symbol_universe_cache

    try:
        from backend.app.data.database import SessionLocal
        from backend.app.data.repositories.symbol_universe_repo import SymbolUniverseRepository

        db = SessionLocal()
        try:
            repo = SymbolUniverseRepository(db)
            _symbol_universe_cache = repo.get_symbols_set(active_only=True)
            logger.debug(f"Loaded {len(_symbol_universe_cache)} symbols from universe")
            return _symbol_universe_cache
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Failed to load symbol universe: {exc}")
        return set()


def clear_symbol_universe_cache() -> None:
    """Clear the symbol universe cache (call after refreshing universe)."""
    global _symbol_universe_cache
    _symbol_universe_cache = None


def extract_tickers(
    text: str,
    known_symbols: Set[str] | None = None,
    use_symbol_universe: bool = True,
) -> Set[str]:
    """Extract potential stock ticker symbols from text.

    Uses a simple regex pattern to find ticker-like strings. If known_symbols
    is provided, only returns tickers that are in that set. Otherwise, uses
    symbol universe as whitelist if available, or extracts all potential tickers
    (filtering out common words).

    Args:
        text: The text to search for tickers.
        known_symbols: Optional set of valid stock symbols to filter results.
                      If None and use_symbol_universe is True, loads from database.
        use_symbol_universe: Whether to use symbol universe as whitelist if
                            known_symbols is None.

    Returns:
        Set of extracted ticker symbols (uppercase, without $ prefix).
    """
    matches = TICKER_PATTERN.findall(text.upper())
    tickers = {match for match in matches if len(match) >= 1}

    # Filter out common words that aren't stocks
    tickers = tickers - COMMON_WORDS

    # Determine whitelist to use
    if known_symbols is not None:
        whitelist = known_symbols
    elif use_symbol_universe:
        whitelist = load_symbol_universe_from_db()
        # If universe is empty, fall back to auto-discovery mode
        if not whitelist:
            logger.debug("Symbol universe is empty, using auto-discovery mode")
            return tickers
    else:
        # Auto-discovery mode: return all potential tickers
        return tickers

    # Filter by whitelist
    if whitelist:
        tickers = tickers.intersection(whitelist)

    return tickers

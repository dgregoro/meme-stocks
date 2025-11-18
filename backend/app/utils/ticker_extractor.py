from __future__ import annotations

import re
from typing import Set

# Common stock ticker pattern: 1-5 uppercase letters, possibly with $ prefix
# This is a simple regex; can be enhanced with a whitelist of valid tickers
TICKER_PATTERN = re.compile(r"\$?([A-Z]{1,5})\b")


def extract_tickers(text: str, known_symbols: Set[str] | None = None) -> Set[str]:
    """Extract potential stock ticker symbols from text.

    Uses a simple regex pattern to find ticker-like strings. If known_symbols
    is provided, only returns tickers that are in that set.

    Args:
        text: The text to search for tickers.
        known_symbols: Optional set of valid stock symbols to filter results.

    Returns:
        Set of extracted ticker symbols (uppercase, without $ prefix).
    """
    matches = TICKER_PATTERN.findall(text.upper())
    tickers = {match for match in matches if len(match) >= 1}

    if known_symbols is not None:
        tickers = tickers.intersection(known_symbols)

    return tickers


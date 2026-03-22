"""Curated bootstrap dataset for stock groups (leader-follower candidate universe).

This is scaffolding for the leader-follower pipeline. stock_groups is the candidate
universe: when a leader is detected, other symbols in the same group become follower
candidates. Without groups, follower candidate generation returns zero.

Edit this file to add or remove groups. Run `python -m backend.app.cli seed stock-groups`
to apply changes idempotently.
"""

from __future__ import annotations

# group_id -> list of stock symbols
BOOTSTRAP_GROUPS: dict[str, list[str]] = {
    "semis": [
        "NVDA",
        "AMD",
        "MU",
        "AVGO",
        "QCOM",
        "INTC",
        "AMAT",
        "LRCX",
        "KLAC",
        "ON",
    ],
    "banks": [
        "JPM",
        "BAC",
        "WFC",
        "C",
        "GS",
        "MS",
    ],
    "oil": [
        "XOM",
        "CVX",
        "COP",
        "EOG",
        "OXY",
        "SLB",
    ],
    "megacap_tech": [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
    ],
    "meme": [
        "GME",
        "AMC",
        "BB",
    ],
}

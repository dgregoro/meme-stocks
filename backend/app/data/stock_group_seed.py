"""Curated bootstrap dataset for stock groups (leader-follower candidate universe).

These are curated bootstrap peer groups for the leader-follower pipeline:
- Intentionally conservative to improve candidate coverage without broad market noise
- Bias toward liquid, recognizable names with clear peer relationships
- Future evolution may move toward pair-level or learned relationships

stock_groups is the candidate universe: when a leader is detected, other symbols
in the same group become follower candidates. Without groups, follower candidate
generation returns zero.

Edit this file to add or remove groups. Run `python -m backend.app.cli seed stock-groups`
to apply changes idempotently.
"""

from __future__ import annotations

# group_id -> list of stock symbols (liquid, established sector names)
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
        "MCHP",
        "MPWR",
        "TXN",
        "SWKS",
        "QRVO",
        "ADI",
        "NXPI",
        "TER",
        "ASML",
        "MRVL",
    ],
    "banks": [
        "JPM",
        "BAC",
        "WFC",
        "C",
        "GS",
        "MS",
        "USB",
        "PNC",
        "TFC",
        "BK",
        "SCHW",
        "COF",
        "AXP",
    ],
    "oil": [
        "XOM",
        "CVX",
        "COP",
        "EOG",
        "OXY",
        "SLB",
        "HAL",
        "PSX",
        "MPC",
        "VLO",
        "DVN",
        "FANG",
        "APA",
    ],
    "megacap_tech": [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "ORCL",
        "CRM",
        "ADBE",
        "NFLX",
        "NOW",
        "IBM",
    ],
    "meme": [
        "GME",
        "AMC",
        "BB",
        "KOSS",
        "BYND",
    ],
    # Liquid benchmarks for regime research and daily-strategy evaluation (e.g. SPY).
    "benchmarks": [
        "SPY",
    ],
}

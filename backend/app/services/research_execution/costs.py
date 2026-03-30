"""Shared transaction cost helpers for research simulations (percent return space)."""


def apply_round_trip_cost(gross_return_pct: float, per_trade_cost_pct: float) -> float:
    """Subtract one round-trip cost (percentage points) from gross return."""
    return gross_return_pct - per_trade_cost_pct


def round_trip_cost_pct_from_bps(bps: float) -> float:
    """Convert basis points to percentage points (e.g. 10 bps -> 0.1%)."""
    return float(bps) / 100.0

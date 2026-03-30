"""Shared building blocks for research simulations and walk-forward evaluation.

- :mod:`backend.app.services.research_execution.costs` — round-trip cost in percent space
- :mod:`backend.app.services.research_execution.metrics` — drawdown, compound equity
- :mod:`backend.app.services.research_execution.window_splits` — calendar / trading-day chunks
- :mod:`backend.app.services.research_execution.run_envelope` — reproducibility metadata
- :mod:`backend.app.services.research_execution.daily_simple_backtest` — long-only daily signal path
- :mod:`backend.app.services.research_execution.walk_forward_harness` — window orchestration
"""

from backend.app.services.research_execution.costs import (
    apply_round_trip_cost,
    round_trip_cost_pct_from_bps,
)
from backend.app.services.research_execution.daily_simple_backtest import (
    DailyBar,
    DailySimpleBacktestConfig,
    DailySimpleBacktestResult,
    DailySimpleSkip,
    DailySimpleTrade,
    daily_simple_result_to_jsonable,
    run_daily_simple_long_only_backtest,
)
from backend.app.services.research_execution.metrics import (
    compound_equity_from_period_returns,
    max_drawdown_from_equity,
)
from backend.app.services.research_execution.run_envelope import ResearchRunEnvelope
from backend.app.services.research_execution.walk_forward_harness import (
    WalkForwardWindowResult,
    run_walk_forward_windows,
)
from backend.app.services.research_execution.window_splits import (
    split_calendar_range,
    split_sorted_trading_days,
)

__all__ = [
    "DailyBar",
    "DailySimpleBacktestConfig",
    "DailySimpleBacktestResult",
    "DailySimpleSkip",
    "DailySimpleTrade",
    "ResearchRunEnvelope",
    "WalkForwardWindowResult",
    "apply_round_trip_cost",
    "compound_equity_from_period_returns",
    "daily_simple_result_to_jsonable",
    "max_drawdown_from_equity",
    "round_trip_cost_pct_from_bps",
    "run_daily_simple_long_only_backtest",
    "run_walk_forward_windows",
    "split_calendar_range",
    "split_sorted_trading_days",
]

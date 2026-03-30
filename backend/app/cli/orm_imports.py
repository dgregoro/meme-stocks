"""Import all ORM modules so `Base.metadata` is complete before `init_db()`."""

from __future__ import annotations

from backend.app.models import (  # noqa: F401
    daily_strategy_merit_run,
    intraday_ingest_run,
    intraday_ingest_state,
    job_execution,
    job_lock,
    job_run_history,
    leader_event,
    leader_follower_candidate,
    leader_follower_optimization_result,
    leader_follower_optimization_run,
    leader_follower_robustness_aggregate,
    leader_follower_robustness_run,
    leader_follower_robustness_split_result,
    leader_follower_paper_run,
    leader_follower_paper_trade,
    leader_follower_signal,
    notification,
    paper_trade,
    price_data,
    price_labels,
    stock,
    stock_group,
    symbol_universe,
    volume_spike_event,
    vol_term_structure_observation,
    extreme_move_event,
)

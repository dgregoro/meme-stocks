# Slice: Integration conventions (CLI, merit, recipes)

**Status:** 🔄 Ongoing — documents how 020 relates to existing CLI and persistence.

## CLI

- **Daily strategy:** `python -m backend.app.cli evaluate daily-strategy …` — preflight **019**; merit persistence `daily_strategy_merit_runs`; optional `--no-persist`.
- **Strategy catalog:** `strategies list`, `strategies merit-runs list|show`.
- **Research recipes (018):** YAML steps may call evaluate commands; future: optional `envelope:` block forwarded as env or JSON sidecar (see `run-envelope.md` Planned).

## Code import graph (intended)

```
strategy-specific services
    → research_execution (costs, metrics, splits, envelope)
    → repositories (price_data, stocks, …)
leader_follower_paper_trading_service
    → research_execution.costs, research_execution.metrics
daily_frequency_strategy_research
    → research_execution.window_splits
```

**Anti-pattern:** importing `leader_follower_paper_trading_service` from generic daily-strategy code to reuse cost math — use `research_execution` instead.

## Merit run persistence

- Table: `daily_strategy_merit_runs` — full `report_json` + index columns.
- **Optional future:** top-level `run_envelope` inside `report_json` or dedicated column per `run-envelope.md`.

## Testing

- **Unit:** pure helpers in `test_research_execution.py`.
- **Integration:** merit rolling still passes `test_daily_strategy_merit.py`; leader-follower `test_leader_follower_paper_trading_service.py` unchanged in behavior after refactor.

## Documentation sync

When adding a new consumer of `research_execution`:

1. Update `docs/ARCHITECTURE.md` § Shared research execution if the **capability** changes.
2. Update `docs/ROADMAP.md` if user-visible behavior or scope changes.

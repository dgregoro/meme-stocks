# Phase 0 — Research: 020 Shared research execution

## Decisions

### R-001: Centralize cost and drawdown in `research_execution`

- **Decision**: Move `apply_round_trip_cost` and `max_drawdown_from_equity` from `leader_follower_paper_trading_service` into `research_execution`; leader-follower imports them.
- **Rationale**: Single source of truth for percent-return semantics across strategy families.
- **Alternatives considered**: Leave duplicated one-liners (rejected — drift risk).

### R-002: Window splits as pure functions

- **Decision**: `split_calendar_range` and `split_sorted_trading_days` live in `research_execution/window_splits.py`; daily merit imports them.
- **Rationale**: Walk-forward harness and future CLI can reuse without SQLAlchemy session.
- **Alternatives considered**: Keep private functions only in `daily_frequency_strategy_research` (rejected — blocks generic harness).

### R-003: Run envelope vs full experiment tracking

- **Decision**: Lightweight `ResearchRunEnvelope` JSON; optional embed in merit JSON later; no mandatory new DB column in v1.
- **Rationale**: Matches personal-use / incremental roadmap; avoids migration until needed.
- **Alternatives considered**: Dedicated `research_runs` table with FK everywhere (deferred).

### R-004: Daily simple backtest — v1 scope

- **Decision**: Long-only MVP, daily bars, explicit skip on missing data, costs via existing percent helpers.
- **Rationale**: Unblocks S1/S2-style rules without copying 011 signal schema.
- **Alternatives considered**: Full shorting and borrow (out of scope for first implementation).

### R-005: Walk-forward harness — v1 scope

- **Decision**: Serial execution only; callback interface; collect per-window errors; no parallelism.
- **Rationale**: Simplicity and debuggability on SQLite.

## Resolved clarifications (no NEEDS CLARIFICATION remaining)

- **Spec Kit branch**: Use `SPECIFY_FEATURE=020-shared-research-execution` when on `main`, or check out a git branch named `020-*` per `.specify/scripts/bash/common.sh`.
- **Testing**: `pytest` + `./scripts/verify.sh` per constitution.

## References

- Slice specs: `core-helpers.md`, `run-envelope.md`, `daily-simple-backtest.md`, `walk-forward-harness.md`, `net-metrics-reporting.md`, `integration-conventions.md`
- `docs/ARCHITECTURE.md` — Shared research execution subsection

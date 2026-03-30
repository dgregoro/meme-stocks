# Slice: Walk-forward harness (orchestration)

**Status:** 📋 Planned — partial primitives exist; **no** generic orchestrator service.

## Existing building blocks

- **`research_execution.window_splits`** — equal calendar or equal **trading-day-count** chunks inside `[eval_start, eval_end]`.
- **`rolling_split_utils.generate_monthly_rolling_splits`** — train /Validate / optional test **month-based** windows for leader-follower robustness.
- **Daily merit rolling** — runs merit per chunk and rollups (`run_s1_merit_rolling_report`, etc.).

## Purpose

A **generic harness** that:

1. Accepts a **window plan** (calendar chunks, trading chunks, or monthly rolling splits from `rolling_split_utils`).
2. For each window, invokes a **user-supplied callback** (e.g. merit report, simple backtest from `daily-simple-backtest.md`, or custom JSON).
3. Emits a **stable JSON shape**: list of `{window, metrics, errors}` plus optional **cross-window rollup** (e.g. fraction of windows with positive net excess).

## Requirements (target)

- **No** strategy math inside the harness — only scheduling + error aggregation.
- **Failure isolation:** one bad window does not crash entire run unless `--strict` (TBD); default: collect errors per window.
- **Configurable:** max windows, parallelization **out of scope** for v1 (serial only).

## Non-goals

- Replacing **010/012** optimization grids (those stay leader-follower scoped).
- Automatic hyperparameter search (separate concern).

## Acceptance (when implemented)

- Unit test: 3 synthetic windows, callback returns incrementing int, harness returns list of 3 results in order.
- Integration test (optional): harness + `split_calendar_range` + mocked inner eval.

# Slice: Daily simple backtest (generic signal → PnL)

**Status:** 📋 Planned — not implemented.

## Purpose

Provide a **strategy-agnostic** simulator on **daily `price_data`** that turns a sequence of **signals** (or **target weights**) into **period returns** and **equity curve**, using shared **`research_execution`** costs/metrics where applicable.

**Different from:**

- **S1/S2 merit** — descriptive pooled buckets vs baseline, not a full portfolio path.
- **011 Leader-follower paper** — event-driven from `LeaderFollowerSignal` rows with domain-specific entry/exit.

## Requirements (target)

### Inputs (conceptual)

- `symbols`, `[start, end]` trading calendar
- **Signal provider** — callable or iterator: `(date, symbol) -> signal` where `signal` is one of:
  - **Discrete:** `{-1, 0, +1}` or `{flat, long, short}` for long-only MVP use `0|1`
  - **Weight:** `float` in `[0, 1]` for fractional participation (phase 2)
- **Execution model** (configurable, explicit):
  - Entry: `same_close` | `next_open` (align naming with 011 where possible)
  - Exit: `horizon_days` (fixed holding) | `signal_flip` | `next_open_after_horizon`
- **Costs:** `round_trip_cost_bps` or `per_trade_cost_pct` (same percent-space convention as `core-helpers.md`)

### Outputs

- Per-trade or per-period **gross** and **net** return series
- Cumulative equity via `compound_equity_from_period_returns`
- `max_drawdown_from_equity`
- Optional **pandas-free** dict payload for CLI JSON

### Data / reliability

- Missing bar on entry or exit date → **skip** trade with logged reason; **no** interpolation.
- **Idempotent** re-run given same inputs (no randomness unless seed documented).

### Out of scope (v1)

- Short borrow, margin, cash yield
- Multi-asset cross-hedge
- Intraday stops

## Implementation sketch

- New module e.g. `backend/app/services/research_execution/daily_simple_backtest.py` (or `daily_strategy_backtest_service.py`)
- Uses `PriceDataRepository` + sorted trading days per symbol
- Unit tests with synthetic bars in memory (pattern: `test_daily_strategy_merit`)

## Acceptance (when implemented)

- `pytest` **happy path:** two-day holding, long-only, known prices → known gross return
- **Error path:** gap in bars → skip + structured skip reason in output
- **Cost path:** net = gross minus configured round-trip in percent space

# Slice: Core helpers (`research_execution`)

**Status:** ✅ Implemented (`backend/app/services/research_execution/`)

## Scope

Shared **pure functions** and **no-DB** utilities for research simulations and rolling evaluation.

### 1. Costs (`costs.py`)

**Requirements**

- `apply_round_trip_cost(gross_return_pct, per_trade_cost_pct)` subtracts **percentage points** from a **simple percent return** (e.g. gross `+5.0`, cost `0.1` → `4.9`). Same semantics as historical leader-follower `per_trade_cost_pct`.
- `round_trip_cost_pct_from_bps(bps)` converts basis points to percentage points (`10` bps → `0.1`).

**Non-requirements**

- Per-leg fee schedules, exchange rebates, or borrow cost (future extension or domain-specific specs).

### 2. Metrics (`metrics.py`)

**Requirements**

- `max_drawdown_from_equity(equities)` — peak-to-trough drawdown as a **positive** percent of peak, for equity curve starting at arbitrary positive values (same formula as ex–leader-follower inline impl).
- `compound_equity_from_period_returns(returns_fraction)` — equity index starting at `1.0`, each input **simple** return for the period (e.g. `0.01` = +1%).

### 3. Window splits (`window_splits.py`)

**Requirements**

- `split_calendar_range(start, end, n)` — partition **inclusive** calendar `[start, end]` into `n` contiguous sub-ranges; if range shorter than `n`, return full range as single window; never silently drop dates.
- `split_sorted_trading_days(sorted_days, n)` — partition a **sorted** list of `date` into `n` contiguous **index** blocks; empty input → `[]`; `n <= 1` → single window from first to last day.

**Consumers**

- `daily_frequency_strategy_research._merit_rolling_windows` (calendar vs trading modes).

**Tests**

- Covered by `backend/tests/test_research_execution.py` and `backend/tests/test_daily_strategy_merit.py` (split parity).

---

## Migration / ownership

- **Leader-follower** imports costs + drawdown from here (no duplicate implementations).
- **Daily-frequency merit** imports splits from here (removed duplicate `_calendar_splits` / `_trading_day_chunks`).

---

## Future extensions (not required for this slice)

- Optional **partial position** turnover cost (separate function, explicit API).
- **Risk-free** curve for Sharpe (out of scope unless a new slice adds it).

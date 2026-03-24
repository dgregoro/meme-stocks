# Feature Specification: Leader-Follower Execution and Paper Trading

**Feature Name**: leader-follower-execution-and-paper-trading
**Feature ID**: 011
**Created**: 2026-03-24
**Status**: Draft
**Note**: Numbered **011** because **009** is reserved for pair filtering and ranking.

---

## Problem Statement

Leader-follower detection, evaluation, backfill, and pair filtering exist. Event-level evaluation shows a modest edge (e.g. ~58% win rate at 3d, ~0.48% average return per event). That edge must survive **execution costs**, **position limits per event**, and **realistic entry/exit rules** before the strategy can be considered tradable.

This feature adds a **simulation layer**: convert historical signals into simulated trades with configurable execution rules, transaction costs, and portfolio-level metrics—without live brokerage integration.

---

## Goals

- Convert `leader_follower_signals` + `price_data` into simulated trades with explicit entry/exit prices and returns.
- Make execution rules and costs **configurable** and **deterministic** (same inputs → same outputs).
- Support **event-based position caps** (top N followers per leader event).
- Expose results via **API** and **CLI** for analysis.

---

## Non-Goals

- No live trading or brokerage integration.
- No rich UI (API + CLI only).
- No portfolio optimization, leverage, or multi-asset allocation beyond simple equal-notional sequential simulation.
- No options, shorting, or borrow costs (long-only on follower leg unless extended later).

---

## User Stories

### US1 — Simulate trades from signals

As a user, I want signals converted into simulated trades so I can measure realistic P&L.

**Acceptance criteria:**

- Each executed trade records:
  - `entry_price`, `exit_price`
  - `entry_time`, `exit_time` (UTC; typically market-day boundaries for daily bars)
  - `holding_period_days` (trading days between entry and exit dates)
  - `gross_return_pct`, `net_return_pct`

---

### US2 — Configurable execution rules

As a user, I want to define how trades are executed.

**Acceptance criteria:**

- Config options:
  - `entry_mode`: `next_open` | `same_close`
  - `exit_mode`: `fixed_days` | `early_exit`
  - `holding_days` (default `3`)
  - `max_positions_per_event` (default `2`)
  - `min_pair_score` (optional; filters by signal `strength_score` when set)

**Semantics (normative):**

- **`next_open`**: Entry price = follower **open** on the first trading day **strictly after** `signal_date` with a price bar.
- **`same_close`**: Entry price = follower **close** on `signal_date` (skip if bar missing).
- **`fixed_days`**: Exit price = follower **close** on the trading day that is `holding_days` **trading days after** the entry date (entry day = day 0).
- **`early_exit`**: Walk forward from the first trading day after entry; exit at **close** of the first day where `close < entry_price` (simple stop); if not triggered, exit at the same date as `fixed_days`.

---

### US3 — Transaction cost model

As a user, I want transaction costs included.

**Acceptance criteria:**

- `per_trade_cost_pct` (default `0.1`) — **one** round-trip cost subtracted once per trade from gross return (percentage points):
  `net_return_pct = gross_return_pct - per_trade_cost_pct`

---

### US4 — Event-based position selection

As a user, I want to limit trades per leader event to reduce correlated overexposure.

**Acceptance criteria:**

- Group signals by `(leader_symbol, signal_date)`.
- Within each group, rank candidates by:
  1. `strength_score` descending
  2. Tie-break: `leader_return_pct` descending
  3. Tie-break: `follower_symbol` ascending (deterministic)
- Take top `N = max_positions_per_event` after optional `min_pair_score` filter.

---

### US5 — Portfolio simulation

As a user, I want a running portfolio view.

**Acceptance criteria:**

- Equal notional per trade; **sequential compound** equity: start `1.0`, after each trade `equity *= (1 + net_return_pct / 100)`.
- Report: cumulative return %, equity curve (per trade step), max drawdown %, trade count, win rate (net > 0).

---

### US6 — Evaluation API

**Endpoints:**

- `GET /api/leader-follower/paper-trading/runs` — list runs (recent first).
- `GET /api/leader-follower/paper-trading/{run_id}` — run detail: config, summary metrics, **paginated** trades (`offset`, `limit`).
- `GET /api/leader-follower/paper-trading/{run_id}/equity-curve` — ordered points `{ trade_index, equity }` or `{ after_trade_n, cumulative_return_pct }`.

Errors: structured (404 if run missing), no raw tracebacks.

---

### US7 — CLI integration

```bash
python -m backend.app.cli simulate leader-follower \
  --start 2025-02-01 \
  --end 2026-03-20 \
  --entry next_open \
  --holding_days 3 \
  --max_positions_per_event 2 \
  --cost_pct 0.1
```

CLI uses the same backend service as the API (direct DB + service layer), consistent with `backfill leader-follower` in `backend/app/cli.py`.

---

## Data Model

See [data-model.md](./data-model.md).

---

## Success Criteria

We can answer: **“Does this strategy make money after costs under realistic constraints?”** using cumulative return, drawdown, win rate, and stability over time (manual comparison of multiple date windows).

---

## Dependencies

- `leader_follower_signals`, `price_data` populated (e.g. backfill).
- Stocks/symbols present for price bars used.

---

## Out of Scope (Future)

- Borrow costs, slippage models beyond fixed %, partial fills.
- UI dashboards.

# Feature Specification: Leader-follower regime filtering

**Feature Name**: leader-follower-regime-filtering
**Feature ID**: 014
**Created**: 2026-03-27
**Status**: Implemented
**Branch (suggested)**: `014-leader-follower-regime-filtering`

---

## Executive summary

This feature adds **market regime classification and gating** to leader-follower **execution** (paper trading and any path that simulates trades from stored signals). Trades are only allowed when **simple, explainable** market conditions pass—using **existing daily price data** (benchmark + optional volatility filter + optional reuse of 013 sector checks). There is **no predictive model**, **no ML**, and **no intraday** regime stack. The goal is **fewer regime-dependent failures** and **improved consistency across time splits**, integrated with **walk-forward optimization (`010`)** and **rolling robustness (`012`)** the same way as other `PaperTradingConfig` axes.

---

## Problem statement

- **Strategy performance varies significantly across time splits**: Rolling robustness shows some windows highly profitable and others consistently negative; the system cannot today label or avoid **unfavorable** macro regimes in a structured way.
- **No explicit market context**: Leader-follower signals are simulated without reference to **overall market trend** or **aggregate volatility**, beyond optional sector ETF confirmation (013).
- **013 is insufficient alone**: Sector confirmation can modestly reduce risk on some paths but **does not resolve** instability driven by **broad market** drawdowns or **high-volatility** environments where pair-following may fail.
- **Need a mechanism** to identify and **skip trading** in historically hostile conditions using **transparent rules**, so researchers can **grid-search** regime parameters alongside execution parameters.

---

## Goals

- Introduce **simple, interpretable** regime indicators (benchmark trend, rolling volatility; optional sector strength from 013).
- **Filter trades** based on configurable boolean regime conditions (gate at execution time).
- Aim for **better consistency across splits** (medians, worst splits, fraction of positive windows)—not only maximizing a single-window average return.
- **Reduce catastrophic or persistently negative periods** where the gate can plausibly help (empirical validation via `010`/`012`).
- **Integrate** with existing **`PaperTradingConfig`**, optimization grids, robustness grids, CLI simulate, and paper trade persistence/API.

---

## Non-goals

- **No** machine learning, clustering, HMMs, or learned regime labels.
- **No** high-dimensional feature sets or factor models.
- **No** external macro datasets (Fed, CPI, economic calendars, alternative data APIs).
- **No** prediction of regime **transitions** or next-day regime; only **same-day/as-of** gating from known bars.
- **No** real-time streaming or **intraday** regime detection (daily bars only; align with 013).
- **No** UI/dashboard work.

---

## User stories

### User Story 1: Apply regime filter to trades (Priority: P1)

As a **developer**,
I want to **gate trades based on market conditions**,
so that the strategy **avoids unfavorable environments** when the filter is enabled.

**Acceptance criteria**

- Trades can be **enabled or blocked** based on **evaluated regime conditions** at the same decision point as other execution gates (after signal selection, alongside 013 if both enabled).
- Regime gating is **configurable** and can be **turned off** by default (**backward compatible** brownfield behavior).
- Skips attributable to regime failure are **counted** separately from other skip reasons (e.g. extend metrics with `skipped_regime_filter_count` or equivalent) and included in run summaries.
- Missing benchmark data or insufficient history: behavior is **explicit** (skip trade with logged context, or documented strict mode)—**no silent pass** as default when regime filter is **enabled** (see `research.md` for chosen default).

**Independent test**: Simulation on a fixture with synthetic SPY + follower prices; toggling regime gate changes trade list and skip counts predictably.

---

### User Story 2: Configure regime indicators (Priority: P1)

As a **researcher**,
I want to **tune regime parameters**,
so that I can **evaluate their effect** on performance and robustness.

**Acceptance criteria**

Configurable parameters (stable JSON keys; exact names in `data-model.md`):

| Parameter (illustrative) | Purpose |
|--------------------------|---------|
| `regime_filter_enabled` | bool; master switch |
| `regime_benchmark_symbol` | string; default e.g. `SPY` |
| `market_trend_window` | int; trading days for benchmark MA |
| `require_market_uptrend` | bool; if true, require benchmark close > MA(`market_trend_window`) on decision date |
| `volatility_window` | int; trading days for rolling std of benchmark returns |
| `volatility_threshold` | float; regime allows trade only if rolling std **≤** threshold (or documented comparator) |
| `require_low_volatility` | bool; if false, volatility rule is skipped even if other params set |
| `regime_sector_strength_required` | bool (optional). If true, **reuse** 013 sector confirmation outcome (same snapshot rules as 013) **in addition** to market rules. |

- Invalid combinations (negative windows, unknown symbol format) raise **clear validation errors** at config parse time.
- All fields are part of **`PaperTradingConfig`** (or embedded documented sub-structure flattened into JSON like 013).

**Independent test**: Unit tests for regime math on small price series; `from_json_dict` rejects bad inputs.

---

### User Story 3: Evaluate regime filtering in optimization and robustness (Priority: P2)

As a **researcher**,
I want regime filtering **included in optimization and robustness runs**,
so that I can measure whether it **improves stability** across splits.

**Acceptance criteria**

- Regime-related keys appear in **`ALLOWED_GRID_KEYS`** (walk-forward + rolling loaders) so grids/candidates can vary regime params alongside `holding_days`, 013 flags, etc.
- Reported metrics reflect **only executed** trades after **all** gates (pair score, sector, regime, …).
- Stored run/config JSON includes regime parameters for **reproducibility**.

**Independent test**: Two grid points differ only by `regime_filter_enabled`; results differ in trade counts and returns when the gate binds.

---

### User Story 4: Inspect regime context (Priority: P2)

As a **developer**,
I want to see **regime conditions for each trade** (and clear skip reasons),
so that I can **understand** when trades are allowed or blocked.

**Acceptance criteria**

- **Paper trades** persist **nullable regime snapshot fields** (e.g. benchmark close, MA, rolling vol, booleans passed/failed, optional sector pass flag if combined).
- **API** responses for paper trades expose these fields (additive; PRD Appendix C for errors).
- Skipped-by-regime events are reflected in **aggregate counters** on the paper run row where applicable.

**Independent test**: API/CLI shows non-null regime fields when gate enabled and data exists.

---

## Functional requirements

### FR-1. Market regime indicators (benchmark)

Use **daily** `price_data` for a configurable benchmark symbol (default **`SPY`**).

1. **Market trend**
   - Compute **simple moving average** of benchmark **close** over `market_trend_window` **prior** trading days ending on the **decision date** (entry-date alignment: same calendar convention as 013—no leakage).
   - **Uptrend** (when `require_market_uptrend` is true): benchmark **close on decision date** **>** MA.

2. **Volatility** (when `require_low_volatility` is true)
   - Compute **rolling standard deviation** of benchmark **daily returns** over `volatility_window` trading days ending on decision date (window length = `volatility_window`).
   - Return definition and std flavor (simple returns; population std in code): **`research.md`**.
   - **Low volatility**: rolling std **≤** `volatility_threshold` (unitless decimal of daily simple-return std; see `research.md`).

3. **Optional sector strength**
   - When `regime_sector_strength_required` is true, **and** sector confirmation parameters are applicable, the trade passes only if **both** market regime rules pass **and** the 013 sector check passes for that signal (reuse `evaluate_sector_confirmation` or equivalent—**no duplicate math**).

### FR-2. Regime classification (boolean logic)

- **No** multi-class regime labels for MVP; **only** pass/fail for “allowed to open trade.”
- **Example** (illustrative; exact composition is configurable via the bool flags above):

```text
market_uptrend = (close_benchmark > MA_N)   # when require_market_uptrend
low_volatility = (rolling_std_W <= threshold)   # when require_low_volatility
sector_ok      = sector_confirmation_passed    # when regime_sector_strength_required
allow_trade    = market_uptrend AND low_volatility AND sector_ok   # only enabled clauses participate
```

- Order of evaluation: **deterministic**; short-circuit permitted for performance **if** logged snapshot still reflects all computed fields needed for persistence (or document partial snapshot when short-circuit).

### FR-3. Gating integration point

- Apply regime gate in **`leader_follower_paper_trading_service`** (or dedicated **`regime_filter_service`**) **after** entry date resolution. **Order with 013** (when both enabled): **sector confirmation first**, then **regime filter**—documented in `research.md` and `quickstart.md`; separate skip counters avoid double-counting in metrics.

### FR-4. Persistence and observability

- Additive columns (or JSON subdocument) on **`leader_follower_paper_trades`** for regime snapshot fields; SQLite migration in `database.py`.
- Add **`skipped_regime_filter_count`** (or name per `data-model.md`) on **`leader_follower_paper_runs`** and extend **`PaperSimulationMetrics`** accordingly.
- Logging: **warning** on missing benchmark series; **no** silent default to “pass.”

### FR-5. Configuration and grids

- Default: `regime_filter_enabled=false`.
- Extend **`ALLOWED_GRID_KEYS`** in `leader_follower_walk_forward_service.py` (and robustness path that reuses it).
- CLI `simulate leader-follower` should expose minimal flags or rely on JSON config path in a follow-up task if out of scope for MVP—**spec prefers** parity with 013 CLI toggles (`plan.md`).

### FR-6. Brownfield compatibility

- With regime filter **off**, behavior matches **pre-014** within numerical tolerance on representative fixtures.
- Does **not** change leader-follower **detection**; only execution/simulation paths.

---

## Key entities (conceptual)

- **Regime snapshot**: benchmark symbol, as-of date, close, MA value, rolling vol, flags for each active rule, combined `regime_filter_passed`.
- **Extended paper trade**: existing row + `regime_*` fields.
- **Extended paper run / metrics**: regime skip count.

---

## Edge cases

- **Benchmark symbol missing** in `price_data`: treat as **fail** when regime enabled (conservative) **or** documented alternative; default **fail**.
- **Window longer than history**: insufficient data → **fail** when regime enabled.
- **013 off but `regime_sector_strength_required` true**: validation error at config parse, or treat sector clause as auto-pass with warning—**choose one in research.md** (recommend **validation error**).
- **Interaction with unmapped sector** when sector clause required: follow 013 documented behavior for sector pass/fail.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Over-filtering kills trades | Default off; wide thresholds in research grids |
| Look-ahead bias | Unit tests on calendar boundaries; only past bars |
| Parameter explosion | Keep MVP to SPY + 2 windows + one threshold |
| Confusion with 013 | Clear ordering and separate skip counters |

---

## Open questions (plan/research)

1. ~~Exact **units** for `volatility_threshold`~~ — **Resolved** in `research.md` (unitless decimal std of simple daily returns).
2. **Evaluation service (007)** extension vs paper-only persistence for MVP.
3. Should **benchmark** be grid-able per run (`regime_benchmark_symbol` in grid) or fixed to SPY for MVP?

---

## Success criteria

- [x] Regime filter **off**: metrics match pre-014 within tolerance on shared fixtures.
- [x] Regime filter **on**: auditable skip counts and stored snapshots on trades.
- [x] At least one **optimization/robustness** grid varies regime params and produces **different** outcomes when the gate binds.
- [x] **API** documents new nullable fields (see `contracts/`).

---

## Requirements traceability

- **FR-014-001**: Price-only benchmark trend and volatility from `price_data`.
- **FR-014-002**: Boolean regime gate at paper execution; configurable enable/disable.
- **FR-014-003**: Optional composition with 013 sector confirmation.
- **FR-014-004**: Persistence on paper trades + run/metrics counters.
- **FR-014-005**: Grid keys for `010`/`012`.
- **FR-014-006**: Tests for pure regime math + gated simulation path.

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| 013 sector confirmation | Optional **AND** condition via `regime_sector_strength_required` |
| 011 paper trading | Primary integration surface |
| 010 / 012 | New `ALLOWED_GRID_KEYS` |

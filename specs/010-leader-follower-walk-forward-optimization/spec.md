# Feature Specification: Leader-Follower Walk-Forward Optimization

**Feature Name**: leader-follower-walk-forward-optimization
**Feature ID**: 010 (walk-forward optimization; distinct from `010-event-level-evaluation`)
**Created**: 2026-03-24
**Status**: Draft
**Branch (suggested)**: `010-leader-follower-walk-forward-optimization`

---

## Executive summary

This feature adds **research-grade walk-forward optimization** for the existing leader-follower stack: explicit train / validation / optional test windows, a **small** parameter grid, **robustness-first** ranking, persisted runs and per-configuration results, plus **CLI-first** execution and **read-only** HTTP APIs for inspection. It **reuses** the current paper-trading simulation (`PaperTradingConfig`, `run_paper_trading_simulation`) and existing signals, prices, and evaluation building blocks wherever possible. It is **not** production auto-tuning, ML, or a general quant platform.

---

## Problem statement

- **Parameter sensitivity**: Strategy outcomes depend on choices such as leader detection thresholds, pair filtering, holding period, per-event trade caps, and cost assumptions. Manual tuning is error-prone and tends to **overfit** to the window one happens to stare at.
- **Need for discipline**: We need a structured **walk-forward** process that separates:
  - **Training period**: where we search over a modest parameter grid;
  - **Validation period**: where we check whether settings **hold up out-of-sample** (chronologically after train);
  - **Optional test period**: a final, untouched window for a conservative read on generalization.
- **Goal of the exercise**: Identify settings that **generalize** and show **stability across periods**, not settings that maximize a single backtest spike. Raw paper trading with broad signal usage has already underperformed; historical and event-level evaluation suggest a possible modest edge (e.g. around **3-day** holding)—this tooling is meant to explore that **without** treating the backtest as the truth.

---

## Goals

- Support **walk-forward optimization** with explicit **train / validate / optional test** date ranges.
- Evaluate a **small, intentional** grid of parameter combinations (not hundreds of dimensions).
- **Rank** candidate sets by **robustness** (validation-first, stability, risk, sample size)—**not** by peak in-sample return alone.
- **Reuse** the existing paper trading simulation pipeline (`backend.app.services.leader_follower_paper_trading_service`) with **controlled** parameter overrides.
- Make optimization **inspectable and reproducible**: stored runs, frozen grid definitions, deterministic ranking inputs.
- Provide **CLI** for batch runs and **read-only** APIs for listing runs and inspecting top results.

---

## Non-goals

- **No** fully automated production tuning or online retuning of live systems.
- **No** black-box ML (neural nets, trees, reinforcement learning, Bayesian optimization as a required path).
- **No** large-scale brute force across hundreds or thousands of hyperparameter combinations.
- **No** advanced portfolio optimization, multi-strategy allocation, or live trading integration.
- **No** rich UI; tables/JSON/API responses are sufficient.
- **No** requirement to “beat” every subperiod; the tool is for **research transparency**, not marketing a best number.

---

## User stories

### User Story 1: Run walk-forward optimization

As a **developer or researcher**,
I want to run an optimization over defined historical periods,
so that I can compare a **limited** set of parameter configurations under walk-forward rules.

**Acceptance criteria**

- CLI supports explicit (ISO date) bounds:
  - `train_start`, `train_end`
  - `validate_start`, `validate_end`
  - optional `test_start`, `test_end`
- The run **evaluates** the configured parameter grid and **persists** the run metadata and per-configuration results (see persistence model).
- Invalid date ranges are rejected with clear rules (see functional requirements).

---

### User Story 2: Tune key parameters

As a **developer or researcher**,
I want to tune a **small** set of meaningful parameters,
so that I can search for **stable** settings without exploding the grid.

**Acceptance criteria**

- Supported parameters include a **practical subset** aligned with the current codebase, for example:
  - **Leader return threshold** (detection-level; see open questions if this implies signal regeneration)
  - **Leader volume threshold** (detection-level; same caveat)
  - **`holding_days`** — `PaperTradingConfig.holding_days` (simulation-level)
  - **`max_positions_per_event`** — `PaperTradingConfig.max_positions_per_event`
  - **`min_pair_score`** / pair filter strength — `PaperTradingConfig.min_pair_score` (filters existing signals by `strength_score`)
  - **`pair_filter_mode` or equivalent** — categorical: e.g. off / filtered / top-only (mapped to existing behavior; see open questions)
  - **`cost_pct`** — `PaperTradingConfig.per_trade_cost_pct` (optional **sensitivity** axis; may be fixed in MVP)
- Grid size remains **intentionally modest**; the spec **discourages** excessive combinations (documented guardrails).

---

### User Story 3: Rank by robustness

As a **developer or researcher**,
I want results ranked by **stability across periods**,
so that fragile but lucky parameter sets are not selected.

**Acceptance criteria**

- Ranking incorporates (at minimum conceptually):
  - **Validation** performance (primary out-of-sample signal for selection)
  - **Train vs validation consistency** (penalize large degradation)
  - **Drawdown** (penalize excessive drawdown)
  - **Trade count / minimum sample size** (penalize too few trades; avoid “great” metrics on tiny samples)
- The system **must not** rank purely by **maximum in-sample (train) cumulative return**.

---

### User Story 4: Inspect top parameter sets

As a **developer or researcher**,
I want to inspect the **top** parameter configurations by robustness,
so that I can **choose** one deliberately for further research.

**Acceptance criteria**

- CLI and/or API can return **top N** configs with:
  - parameter values (JSON)
  - **train** metrics
  - **validation** metrics
  - **optional test** metrics (if test window configured)
  - **robustness score** and **rank** (and enough detail for the ranking to be **explainable**)

---

### User Story 5: Preserve reproducibility

As a **developer or researcher**,
I want optimization runs to be **reproducible**,
so that results can be trusted and compared over time.

**Acceptance criteria**

- Each run stores:
  - parameter grid definition (serialized)
  - all date ranges
  - ranking method identifier + parameters (e.g. weights, floors)
  - per-configuration metrics and scores
- **Re-running** the same inputs with the **same** stored signals, prices, and code version **yields** the same stored outputs (determinism requirement; see risks if signal regeneration is introduced).

---

## Functional requirements

### 1. Walk-forward split support

- Support explicit **train**, **validation**, and **optional test** windows.
- **Chronological ordering**: `train_end < validate_start`, `validate_end < test_start` if test is present; each window’s start ≤ end.
- **Non-overlap**: train, validation, and test windows **must not overlap** (pairwise).
- **Validation and test** must be **after** training in calendar time (no future data in training for validation/test labels).
- Reject invalid splits with structured, user-facing errors (consistent with PRD Appendix C patterns used elsewhere).

### 2. Parameter grid definition

- Allow a **small** grid over selected parameters.
- **Example** candidate ranges (for planning only; **not** hardcoded in application defaults):
  - `leader_return_threshold`: e.g. `[3, 4, 5, 6]` (units must match detection config, e.g. percent)
  - `leader_volume_threshold`: e.g. `[1.2, 1.5, 2.0]`
  - `holding_days`: e.g. `[1, 3, 5]`
  - `max_positions_per_event`: e.g. `[1, 2]`
  - `pair_filter_mode`: e.g. `off | filtered | top_only` (exact mapping to code TBD in plan)
- The product **must** document recommended **maximum** grid size or combination count for v1 to avoid accidental overfitting and runaway compute.

### 3. Reuse existing simulation pipeline

- Optimization **must** call into the existing paper trading simulation (`run_paper_trading_simulation` / `PaperTradingConfig`) rather than reimplementing P&L, drawdown, or trade selection.
- Parameter overrides **must** be applied in one documented layer (e.g. only `PaperTradingConfig` fields vs. also triggering replay)—see open questions.

### 4. Metrics captured per configuration

At minimum per **period** (train, validate, test):

- `total_trades`
- `cumulative_return_pct`
- `avg_return_pct`
- `win_rate`
- `max_drawdown_pct`

Store period-specific aggregates in structured JSON on the result row (see persistence model).

### 5. Robustness ranking

- Define a **simple, explainable** ranking method (documented in spec/plan, not a hidden heuristic).
- Prefer patterns such as:
  - **Validation-first** primary score
  - Penalties for **large train→validation degradation**
  - Penalties for **low trade count** below a floor
  - Penalties for **excessive drawdown**
- Rank field(s) must be **stable** for a given run (deterministic tie-breakers, e.g. lexicographic on params).

### 6. Persistence model

Introduce entities (names illustrative; align with SQLAlchemy conventions in repo):

**`LeaderFollowerOptimizationRun`**

| Field | Description |
|--------|-------------|
| `id` | Primary key |
| `created_at` | UTC timestamp |
| `config_json` | Full grid + CLI options + code/git reference if stored |
| `train_start`, `train_end` | Dates |
| `validate_start`, `validate_end` | Dates |
| `test_start`, `test_end` | Nullable |
| `ranking_method` | Identifier + serialized parameters |

**`LeaderFollowerOptimizationResult`**

| Field | Description |
|--------|-------------|
| `id` | Primary key |
| `run_id` | FK to run |
| `params_json` | One grid point |
| `train_metrics_json` | Metrics for train window |
| `validate_metrics_json` | Metrics for validation window |
| `test_metrics_json` | Nullable |
| `robustness_score` | Float (or decimal) |
| `rank` | Integer (1 = best under method) |

Indexes: by `run_id`, `(run_id, rank)`.

### 7. CLI support

Add a command aligned with existing Typer layout, e.g. under `optimize` or nested under `simulate`:

```bash
python -m backend.app.cli optimize leader-follower \
  --train-start 2025-02-01 \
  --train-end 2025-10-31 \
  --validate-start 2025-11-01 \
  --validate-end 2026-01-31 \
  --test-start 2026-02-01 \
  --test-end 2026-03-20
```

Exact flags may mirror existing `--start`/`--end` patterns in `simulate leader-follower` and `backfill leader-follower`. Grid definition may be **JSON file** or structured flags—decision deferred to plan (must stay simple).

### 8. Read-only API support

| Endpoint | Purpose |
|----------|---------|
| `GET /api/leader-follower/optimization/runs` | List optimization runs (pagination, sort by `created_at` desc). Optional filters: date created, ranking method. |
| `GET /api/leader-follower/optimization/{run_id}` | Full run metadata: windows, grid summary, ranking method, counts. |
| `GET /api/leader-follower/optimization/{run_id}/top-results` | Top N results: params, metrics per period, robustness score, rank. Query param: `limit` (default capped). |

**Response shape** (illustrative):

- Run list item: `id`, `created_at`, `train_start`…`test_end`, `result_count`, `ranking_method` (short).
- Run detail: above plus `config_json` (or redacted/large blob), migration-safe versioning field if needed.
- Top results: array of `{ rank, params_json, train_metrics_json, validate_metrics_json, test_metrics_json | null, robustness_score }`.

All **read-only** (no POST/PUT for v1).

### 9. Brownfield compatibility

- Reuse **signal generation** (where unchanged), **pair filtering** (`min_pair_score`, future categorical modes), **evaluation** metrics concepts, and **paper trading** as implemented in:
  - `backend/app/services/leader_follower_paper_trading_service.py`
  - `backend/app/cli.py` (`simulate leader-follower`, `backfill leader-follower`)
  - Related repositories and APIs under `leader_follower` / `leader_follower_paper_trading`
- Avoid a **parallel** research engine; add **orchestration + persistence + ranking** around existing primitives.
- Schema additions should be **incremental** (new tables or additive columns), following existing migration patterns.

---

## Data requirements

- **Historical signals**: `leader_follower_signals` (and related) as consumed today by paper trading.
- **Paper trading engine**: `run_paper_trading_simulation` and persisted paper runs (optimization may use **in-memory** or **ephemeral** simulation calls per grid point to avoid polluting paper-run history—decision in plan; spec allows either if documented).
- **Pair filtering / strength**: `strength_score` on signals; optional global pair filtering flags in config (`enable_pair_filtering_for_signals`, etc.).
- **Price data**: daily bars via existing `PriceDataRepository` as used by simulation.

---

## Risks and tradeoffs

| Risk | Mitigation |
|------|------------|
| **Overfitting** even with walk-forward if the grid or implicit search space is too large | Cap grid size; document robustness-first ranking; treat test period as rare peek |
| **Too few trades** in a split | Minimum trade floors; penalties; explicit warnings in CLI output |
| **Compute cost** | Small grids; optional parallelism limits; avoid redundant signal replay if not needed |
| **Opaque ranking** | Publish formula; version `ranking_method`; store parameters in DB |
| **Confusing “best” run** | Naming and docs stress **stability**, not peak return |

---

## Brownfield constraints

- **v1**: simple, transparent, computationally manageable.
- **CLI-first** workflow; minimal API surface (read-only).
- **No** general-purpose quant platform scope creep.

---

## Open questions

1. **Signals vs regeneration**: Should optimization use **only pre-generated stored signals** (varying only simulation params like `holding_days`, `min_pair_score`), or **regenerate signals per grid point** when leader thresholds change? (Regeneration implies calling backfill/replay per config—accurate but expensive; stored signals—cheap but cannot explore detection thresholds without new signals.)
2. **MVP optimized parameters**: Which subset is in v1 (e.g. simulation-only params first, detection thresholds later)?
3. **`pair_filter_mode`**: Confirm categorical encoding vs two booleans / `min_pair_score` only for MVP.
4. **Optional test period in MVP**: Is test window required from day one or can v1 ship train+validate only with test optional?
5. **`cost_pct`**: Fixed for ranking runs vs explicit sensitivity grid (separate one-off command)?

---

## Out of scope (summary)

- Bayesian optimization, neural nets, online learning, real-time parameter updates, full multi-strategy optimization, live trading.

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| `003` / `007` / `008` Detection, evaluation, backfill | Source of signals and historical windows |
| `009` Pair filtering | Influences which signals exist or how strength is interpreted |
| `010-event-level-evaluation` | Event-level metrics inform interpretation; orthogonal folder name |
| `011` Paper trading | **Primary reuse target** for simulation and metrics |

---

## Success criteria (feature-level)

- A researcher can run a **documented** walk-forward job from CLI, obtain **persisted** results, and retrieve **top-N** robust configs via API without re-running simulation.
- Ranking is **explainable** from stored `ranking_method` and fields on each result.
- Same inputs and data → **same** stored ranks and scores (deterministic).

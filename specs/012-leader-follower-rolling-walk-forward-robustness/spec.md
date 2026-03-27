# Feature Specification: Leader-Follower Rolling Walk-Forward Robustness

**Feature Name**: leader-follower-rolling-walk-forward-robustness
**Feature ID**: 012
**Created**: 2026-03-26
**Status**: Draft
**Branch (suggested)**: `012-leader-follower-rolling-walk-forward-robustness`

---

## Executive summary

This feature adds **rolling walk-forward robustness evaluation** for the leader-follower stack: many chronological **train → validate → (optional test)** splits generated from a single overall date range, the same **modest** parameter grid or **explicit candidate list** evaluated on **each** split, **per-split metrics** persisted, and **aggregate consistency** metrics plus a **transparent** cross-split ranking. It **reuses** `compute_paper_trading_metrics` / `PaperTradingConfig` and patterns from **`010` walk-forward optimization** (grid parsing, caps, validation rules), but is **not** a new trading strategy: it is **robustness evaluation** to reduce reliance on one lucky split and to surface **regime dependence**.

---

## Problem statement

- **Single-split bias**: A single train/validate/test partition is **insufficient** to judge whether a configuration is robust. The existing walk-forward optimizer (`010`) can produce **strong validation** and **weak forward test** on one split—suggesting **overfitting**, **regime dependence**, or noise.
- **Need for repetition**: To distinguish a **consistent** edge from a **one-period fluke**, the same candidates must be evaluated across **multiple rolling windows** with clear, reproducible split definitions.
- **Intent**: This work is **robustness evaluation**, not production auto-tuning. Stability and **consistency across splits** matter more than **peak performance on any single split**.

---

## Goals

- Support **multiple rolling chronological splits** over an overall `[overall_start, overall_end]`.
- **Reuse** existing paper trading metrics (`backend.app.services.leader_follower_paper_trading_service.compute_paper_trading_metrics`) and grid/config handling aligned with **`010`** (`leader_follower_walk_forward_service` patterns: JSON grid, caps, `PaperTradingConfig`).
- Measure **consistency** (medians, fractions of positive splits, degradation), not only **average** or **best** single-split return.
- **Rank** configurations by **cross-split robustness** with an **explainable** formula (documented method id + parameters in stored config).
- Provide **CLI-first** execution and **read-only** APIs, with **persisted** runs, **per-split** rows, and **per-configuration aggregates**.

---

## Non-goals

- **No** new prediction or alpha model.
- **No** online/adaptive production parameter updates.
- **No** Bayesian optimization, ML rankers, or black-box scoring.
- **No** exhaustive search beyond the existing **modest grid** discipline (`leader_follower_optimization_max_grid_points` or equivalent cap for this feature).
- **No** rich analytics UI; JSON/tables via API/CLI suffice.
- **No** general-purpose quant platform, intraday regime classification, or live trading integration.

---

## User stories

### User Story 1: Run rolling robustness evaluation

As a **developer or researcher**,
I want to run robustness testing across **multiple rolling** time splits,
so that I can see whether performance **generalizes** beyond one partition.

**Acceptance criteria**

- CLI supports (ISO dates and/or **hour-neutral** calendar units):
  - `overall_start`, `overall_end`
  - **Train window** size: `train_window_days` or `train_window_months` (spec defines one MVP primary; see open questions)
  - **Validate window** size: `validate_window_days` or `validate_window_months`
  - **Optional test window** size: `test_window_days` or `test_window_months`
  - **Step** between consecutive splits: `step_days` or `step_months`
- The system **generates** a list of splits `(train, validate, [test])` chronologically ordered, non-overlapping within each split, stepping forward until the range is exhausted or a minimum data rule fails.
- Invalid or empty split generation yields structured, user-facing errors (PRD Appendix C patterns).

---

### User Story 2: Reuse a parameter grid or candidate set

As a **developer or researcher**,
I want to evaluate a **modest** grid **or** an explicit list of configurations across **all** splits,
so that I can compare robustness **across time** without exploding compute.

**Acceptance criteria**

- **Mode A — Grid**: Reuse the **`010`** JSON shape (`base_config`, `grid`, `ranking` subset where applicable) or a documented shared schema; enforce the same **combination cap** philosophy.
- **Mode B — Candidates**: Accept a JSON file listing explicit `PaperTradingConfig`-compatible objects (length capped, e.g. same order of magnitude as grid cap).
- Total work (**splits × candidates**) must be bounded by configuration with safe defaults and a **hard ceiling** (config or CLI error).

---

### User Story 3: Inspect split-by-split performance

As a **developer or researcher**,
I want **per-split** metrics for each configuration,
so that I can see **stability vs regime dependence**.

**Acceptance criteria**

- For each `(config, split_index)` persist:
  - Train / validate / (optional) test metrics: at least `total_trades`, `cumulative_return_pct`, `avg_return_pct`, `win_rate`, `max_drawdown_pct`
  - Split metadata: `split_index`, `train_start`/`train_end`, `validate_start`/`validate_end`, optional test bounds
- CLI and API can **list** splits and **drill down** into metrics (pagination where needed).

---

### User Story 4: Rank configurations by robustness

As a **developer or researcher**,
I want rankings driven by **consistency across splits**,
so that **one-period winners** are not selected by default.

**Acceptance criteria**

- Aggregate and rank using signals such as:
  - **Median** validation (and optional test) cumulative return across splits
  - **Fraction** of splits with **positive** validation return (and optional test)
  - Penalty for **large train→validation degradation** aggregated across splits (e.g. median or sum of positive gaps)
  - **Drawdown** control (e.g. median max drawdown on validation)
  - **Minimum trade count** per split (floor); configs failing floors get heavily penalized or excluded from “eligible” tier
- Ranking **must not** be dominated by **highest single-split** return only.

---

### User Story 5: Identify regime dependence

As a **developer or researcher**,
I want to see **which splits** helped or hurt,
so that I can assess **regime** stories and future **filtering** ideas (out of scope here).

**Acceptance criteria**

- Stored results label each split with outcomes (e.g. sign of validation/test cumulative return).
- API/CLI expose:
  - count of **positive validation** splits per config
  - count of **positive test** splits (if test present)
  - optional **worst-split** validation return for sanity checks
- Output is **legible** in JSON for downstream tooling (no mandatory UI).

---

## Functional requirements

### 1. Rolling split generation

- Inputs: `overall_start`, `overall_end`, window lengths, step.
- For each rolling position, define contiguous periods: **train**, then **validate**, then optional **test**, strictly chronological and **non-overlapping** within the triple.
- **Step**: advance the **anchor** (e.g. start of train) by `step_size` and repeat until the next full split would exceed `overall_end` or violates minimum length rules.
- Document **calendar rules** (inclusive/exclusive ends, month = calendar month vs 30-day approximation); MVP should pick **one** primary rule set and stick to it for determinism.

### 2. Candidate configuration evaluation

- For each split and each candidate, call **`compute_paper_trading_metrics`** (or equivalent shared helper) with `PaperTradingConfig`—**no** new P&L engine.
- Do **not** require persisting a `LeaderFollowerPaperRun` per evaluation (same principle as `010`).
- Remain **deterministic** given the same DB snapshot and config JSON.

### 3. Per-split metrics

Minimum per period (train / validate / test):

- `total_trades`, `skipped_count` (if available from metrics object), `cumulative_return_pct`, `avg_return_pct`, `win_rate`, `max_drawdown_pct`
- Plus split date bounds and `split_index`.

### 4. Aggregate robustness metrics

Per configuration, compute and store in `aggregate_metrics_json` (illustrative fields):

- `splits_evaluated`
- `positive_validation_splits`, `positive_test_splits` (if test used)
- `frac_positive_validation`, `frac_positive_test`
- `median_validation_cumulative_return_pct`, `median_test_cumulative_return_pct`
- `median_validation_max_drawdown_pct`
- `median_train_to_validation_gap` (or similar degradation summary)
- `worst_validation_cumulative_return_pct` (optional but recommended)
- `ineligible_splits` count (below trade floor)

### 5. Ranking method

- Define method id (e.g. `rolling_robustness_v1`) and stored weights/thresholds in run metadata.
- **Transparent** formula in spec/research when implemented; example structure:
  - Base score from **median validation return** and **fraction positive**
  - Penalties for **median drawdown**, **median degradation**, **low fraction positive**, **ineligible splits**
- **Deterministic** tie-breaking (e.g. lexicographic on canonical `params_json`).

### 6. Persistence model

**`LeaderFollowerRobustnessRun`**

| Field | Type | Notes |
|--------|------|--------|
| `id` | PK | |
| `created_at` | datetime UTC | |
| `overall_start` | date | |
| `overall_end` | date | |
| `train_window_spec` | string JSON | e.g. `{"unit":"months","value":6}` |
| `validate_window_spec` | string JSON | |
| `test_window_spec` | string JSON nullable | |
| `step_spec` | string JSON | |
| `grid_config_json` | text | Full candidate source + caps + optional candidate list |
| `ranking_method` | string | e.g. `rolling_robustness_v1` |

**`LeaderFollowerRobustnessSplitResult`**

| Field | Type | Notes |
|--------|------|--------|
| `id` | PK | |
| `run_id` | FK | |
| `config_hash` | string optional | Stable hash of normalized params |
| `params_json` | text | Full merged config |
| `split_index` | int | 0-based or 1-based (document choice) |
| `train_start`, `train_end` | date | |
| `validate_start`, `validate_end` | date | |
| `test_start`, `test_end` | date nullable | |
| `train_metrics_json` | text | |
| `validate_metrics_json` | text | |
| `test_metrics_json` | text nullable | |

Indexes: `(run_id, split_index)`, `(run_id, config_hash or params)` as appropriate for query patterns.

**`LeaderFollowerRobustnessAggregate`**

| Field | Type | Notes |
|--------|------|--------|
| `id` | PK | |
| `run_id` | FK | |
| `config_hash` | string optional | |
| `params_json` | text | |
| `aggregate_metrics_json` | text | |
| `robustness_score` | float | |
| `rank` | int | 1 = best |

### 7. CLI support

Illustrative command (exact flags to match Typer style in `backend/app/cli.py`):

```bash
python -m backend.app.cli robustness leader-follower \
  --overall-start 2025-02-01 \
  --overall-end 2026-03-20 \
  --train-window-months 6 \
  --validate-window-months 2 \
  --test-window-months 1 \
  --step-months 1 \
  --grid-file optimization_grid.json
```

Support a **candidates file** flag alternative to `--grid-file` when in candidate-list mode.

### 8. Read-only API support

| Endpoint | Purpose |
|----------|---------|
| `GET /api/leader-follower/robustness/runs` | List recent robustness runs; query `limit`. |
| `GET /api/leader-follower/robustness/{run_id}` | Run metadata: windows, step, candidate source summary, split count, ranking method. |
| `GET /api/leader-follower/robustness/{run_id}/top-results` | Top N aggregates (`params`, `aggregate_metrics`, `robustness_score`, `rank`). |
| `GET /api/leader-follower/robustness/{run_id}/splits` | Per-split rows; filters: `config_key` / `params_hash`, `split_index`, pagination. |

Errors: structured `error_detail`; 404 for missing run.

### 9. Brownfield compatibility

- Build on **`leader_follower_walk_forward_service`** (split validation ideas, grid expansion, `compute_paper_trading_metrics`) and **`010`** persistence/API patterns (`leader_follower_optimization` router) as a template—**new** tables for robustness, not overload optimization tables.
- **Incremental** schema; import new models in `main.py` / CLI `init_db` imports.
- **CLI-first**; no production trading or scheduler integration.

---

## Data requirements

- Stored `leader_follower_signals` and `price_data` covering `overall_start`–`overall_end` for all splits.
- Same assumptions as `010`: MVP evaluates **simulation parameters** on **existing signals** unless a future spec adds replay-per-candidate.

---

## Risks and tradeoffs

| Risk | Mitigation |
|------|------------|
| Compute explosion (`splits × candidates`) | Hard cap on product; defaults for modest split counts; clear CLI error |
| Noisy metrics on short splits | Minimum window sizes and trade floors; document in quickstart |
| Hidden regimes | Many small steps vs few large windows—document tradeoff |
| Opaque ranking | Named method + stored weights; no undocumented composite |
| Thin trades | Flag ineligible splits; show in aggregate JSON |

---

## Brownfield constraints

- First version: **simple**, **explainable**, **median/fraction**-heavy aggregates.
- Avoid expanding parameter dimensionality beyond **`010`** norms.
- Do not conflate this feature with **live** strategy execution.

---

## Open questions

- **MVP**: Evaluate **full grid on every split** vs **pre-filtered candidates** from a prior `010` run?
- **Test window**: Required or **optional** in MVP?
- **Minimum trades** per split for inclusion in scoring?
- **Split units**: **Month-based** only for v1, or **day-based** too?
- **Worst-split** return: mandatory in aggregate JSON or optional?
- **config_hash**: algorithm (normalized JSON SHA-256) vs `params_json` only?

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| `010` Walk-forward optimization | Single split; ranking formula inspiration; grid JSON reuse |
| `011` Paper trading | Metrics source; no per-eval paper run rows |
| `012` (this) | Many splits; cross-split aggregates; regime visibility |

---

## Success criteria (feature-level)

- A researcher can run one CLI command, obtain **multiple splits** of results, and retrieve **top configs by consistency** without manual bookkeeping.
- Same inputs and DB → **same** splits and ranks (deterministic).
- API surfaces enough detail to answer: “**On how many splits was validation positive?**” and “**Which splits were negative?**”

---

## Supplement: implementation guidance (informal)

*This section is not a Spec Kit `plan.md` / `tasks.md`; it informs future planning only.*

### Recommended MVP implementation approach

1. **Split engine**: Pure function: `(overall bounds, window specs, step) → list[SplitWindows]`; unit-tested; calendar-month MVP using explicit month arithmetic (stdlib) or a small dependency if the project adds one—must match existing project conventions.
2. **Evaluation loop**: Nested loops `for split in splits: for cfg in candidates: compute_paper_trading_metrics(...)`; batch within one DB session; optional progress logging.
3. **Persistence**: Three tables as above; repos mirroring `leader_follower_optimization_*`; one service `leader_follower_rolling_robustness_service` (name TBD) orchestrating splits → metrics → aggregates → rank.
4. **Ranking v1**: Implement `rolling_robustness_v1` with documented weights; store in `grid_config_json` / run row.
5. **CLI + API**: Typer `robustness leader-follower`; FastAPI router under `/api/leader-follower/robustness` mirroring `010` patterns.

### Likely files/modules affected

| Area | Paths (illustrative) |
|------|----------------------|
| Service | `backend/app/services/leader_follower_rolling_robustness_service.py` |
| Split math | `backend/app/services/rolling_split_utils.py` (optional small module) |
| Models | `backend/app/models/leader_follower_robustness_*.py` |
| Repos | `backend/app/data/repositories/leader_follower_robustness_*_repo.py` |
| API | `backend/app/api/leader_follower_robustness.py` |
| CLI | `backend/app/cli.py` |
| Config | `backend/app/config.py` (caps: max splits × candidates) |
| Main | `backend/app/main.py` (router + model imports) |
| Tests | `backend/tests/test_rolling_robustness_*.py` |

### Top 3 implementation mistakes to avoid

1. **Unbounded `splits × grid_points`** — silently running hours of simulation or OOM-ing SQLite; enforce a **hard product cap** and surface it in CLI help.
2. **Inconsistent calendar math** — off-by-one month boundaries producing overlapping train/validate; write deterministic tests for split generation.
3. **Ranking dominated by one lucky split** — if the formula still maxes single-split return, the feature **fails its purpose**; code review against spec §User Story 4.

### Recommendation: default split sizes (starting point)

For **daily** leader-follower signals and **modest** trade counts, biased toward **not** starving validation:

- **Train**: **4–6 calendar months** (MVP default **6** if month-based).
- **Validate**: **2 months** (enough for several leader events if signal rate is moderate).
- **Test** (optional): **1 month** for a quick forward slice per roll; omit test in first runs if compute is tight.
- **Step**: **1 month** for manageable split count over ~12–14 months of data (roughly **a handful** of splits, not dozens).

Tune with **minimum trade floor**: if validation often has **< N** trades, widen validate or shorten step (documented in quickstart when implemented).

### Recommendation: grid reuse vs explicit candidate set

- **Start with grid reuse** (`010` JSON): fastest path, one file, matches current research workflow, reuses `expand_grid_points` / validation.
- **Add candidate-list mode** as soon as you need to re-score **Top-K from a prior `010` run** without re-specifying the full grid—avoids redundant combinations and aligns with “configs that already looked interesting on one split.”

**Practical sequence**: MVP ships **grid-only** or **grid + small candidate file** behind the same cap; prioritize **grid-only** if scope is tight.

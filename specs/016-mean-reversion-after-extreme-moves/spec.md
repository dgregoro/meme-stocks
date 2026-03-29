# Feature Specification: Mean reversion after extreme moves

**Feature Name**: mean-reversion-after-extreme-moves
**Feature ID**: 016
**Created**: 2026-03-29
**Status**: Draft
**Branch (suggested)**: `016-mean-reversion-after-extreme-moves`

---

## Executive summary

This feature adds a **research-only** pipeline to detect **large single-day percentage moves** from existing daily `price_data`, classify each day as **`extreme_up`** or **`extreme_down`**, **persist** events, and **evaluate** short-horizon **forward returns** (1d / 3d / 5d trading days) to test the hypothesis that **short-term overreactions partially mean-revert**. It intentionally avoids machine learning, portfolio logic, execution, and combination with other signals in MVP. Implementation should **mirror** patterns established for **015 volume-spike** and **007 leader-follower evaluation**: `PriceDataRepository`, `compute_forward_return` (or equivalent trading-day stepping), read-only evaluation APIs, Typer `backfill` / `evaluate` commands, additive SQLite schema, and **docs/SIGNAL_EVALUATION_CHECKLIST.md** as the quality gate before any follow-on work.

---

## Problem statement

- **Leader-follower** and **volume-spike (015)** research did **not** show **stable robustness** under time splits, concentration checks, and median-vs-average scrutiny; chasing complexity without a simpler baseline is low yield.
- A **classic, interpretable hypothesis** remains worth testing: after **extreme daily moves**, prices may **partially revert** over the next few **trading sessions** (overreaction / liquidity shock stories).
- The codebase already has **daily `price_data`**, **evaluation aggregations**, **CLI/API** patterns, and optional **robustness** tooling elsewhere; we need a **narrow, additive** event family to **measure** mean-reversion evidence **without** entangling execution or multi-signal ensembles.

---

## Goals

- **Detect** days where **close-to-close daily return** (vs prior trading day with a bar) exceeds configurable **positive** and **negative** thresholds.
- **Classify** each event as **`extreme_up`** or **`extreme_down`** (two buckets only in MVP).
- **Persist** rows in a dedicated table (**`ExtremeMoveEvent`**) for reproducible backfills and API listing.
- **Evaluate** forward returns at **1d, 3d, 5d** trading days from **event_date** close, consistent with existing evaluation conventions (same anchor choice as 015 / 007 unless research.md documents an intentional difference).
- **Aggregate** by **event_type** and **symbol**; expose **win rate**, **average** and **median** return, **`evaluable_count`** per horizon (missing forward bars excluded, not imputed).
- **Reuse** brownfield infrastructure: config module, structured API errors (PRD Appendix C), repository → service → route layering.

---

## Non-goals

- **No** machine learning, scoring models, or black-box predictors.
- **No** portfolio construction, position sizing, risk limits, or broker integration.
- **No** execution engine, paper-trading simulation for this signal, or alerts in MVP.
- **No** combining with leader-follower, volume-spike, Reddit, or sentiment in MVP.
- **No** intraday bars, gaps-only models, or multi-day “extreme” definitions in MVP (single **daily** return only).
- **No** optimization grids over many thresholds in v1 beyond **documented defaults** and config switches.
- **No** mandatory news, earnings calendar, or sentiment features.

---

## Important framing

- This is **signal research**, not a **production strategy**. Positive metrics are **not** a license to trade without the **signal evaluation checklist** and out-of-sample discipline.
- **Simplicity** beats feature depth: one detection rule, two event types, three horizons.
- **Hypothesis direction** (mean reversion) should be stated in docs and reports; **metrics stay symmetric** (report forward returns as observed; do not hard-code “success = negative after up” in code logic—let analysts interpret).

**Interpretive labels (research language only, not execution):**

- **`extreme_up`**: large positive daily return → *hypothesis*: subsequent returns may be **lower** than random baseline (reversion **down**). Sometimes described as a **candidate short** in narrative; MVP does **not** open positions.
- **`extreme_down`**: large negative daily return → *hypothesis*: subsequent returns may be **higher** (reversion **up**). Sometimes described as a **candidate long** in narrative; MVP does **not** open positions.

---

## User stories

### User Story 1: Detect extreme moves (Priority: P1)

As a **researcher**,
I want to **flag days** where daily return exceeds a **magnitude threshold**,
so that I can study post-event price behavior.

**Acceptance criteria**

- Daily return uses **close / prior close − 1** (percentage stored or computed consistently with 015).
- **Prior close** must exist on the **prior trading day with a bar** for that symbol; otherwise **skip** the day (no silent fabrication).
- **Thresholds** are **configurable** (separate **up** and **down** magnitude, symmetric by default).
- Events are **per (symbol, event_date)** at most once per day.

**Independent test**: Controlled price series crosses ±threshold predictably; sub-threshold days do not emit events.

---

### User Story 2: Classify events (Priority: P1)

As a **researcher**,
I want each persisted event labeled **`extreme_up`** or **`extreme_down`**,
so that **up** and **down** shocks are **not pooled** by default.

**Acceptance criteria**

- `event_type` ∈ {`extreme_up`, `extreme_down`}.
- **`extreme_up`**: return ≥ **+up_threshold_pct** (configurable).
- **`extreme_down`**: return ≤ **−down_threshold_pct** (configurable; default symmetric to up).
- If both could apply (should not occur with symmetric exclusive bands), define **exclusive rule** in research.md (e.g. prioritize larger magnitude).

**Independent test**: Threshold changes flip classification at boundaries.

---

### User Story 3: Evaluate outcomes (Priority: P1)

As a **researcher**,
I want **forward returns** after each event at **1d, 3d, 5d** trading days,
so that I can see whether **mean reversion** shows up in **medians** and **distributions**, not only averages.

**Acceptance criteria**

- Horizons align with existing **trading-day** logic (reuse **`compute_forward_return`** pattern from leader-follower / 015).
- Per horizon: **evaluable_count**, **win_rate** (e.g. return > 0), **avg_return_pct**, **median_return_pct**.
- Breakouts by **event_type** and **symbol** in dedicated API responses.
- Missing forward prices: exclude from that horizon’s stats; **evaluable_count** reflects drops.

**Independent test**: Known price path yields known forward returns for a single event.

---

### User Story 4: Backfill events (Priority: P2)

As a **researcher**,
I want to **backfill** extreme-move events over **[start, end]**,
so that I can reach **sample sizes** that satisfy **docs/SIGNAL_EVALUATION_CHECKLIST.md**.

**Acceptance criteria**

- CLI: **`backfill extreme-move`** (or nested consistently with existing `backfill` Typer group).
- **Idempotent**: unique **(symbol, event_date)** with documented **upsert** or replace-range option.
- Uses **only** `price_data` (and `stocks` universe listing); no new mandatory external API for MVP.

**Independent test**: Second backfill without replace does not duplicate rows.

---

### User Story 5: Inspect via API (Priority: P2)

As a **researcher**,
I want **read-only HTTP** endpoints to list events and evaluation summaries,
so that I can script checks without bespoke SQL.

**Acceptance criteria**

- Query params use **`since_date` / `until_date`** (not `start` / `end`) for consistency with 015.
- Structured errors; no raw tracebacks.
- Pagination / **limit** caps documented (e.g. max 2000 for evaluation load).

**Independent test**: Empty range returns stable JSON, HTTP 200.

---

## Functional requirements

### FR-1. Extreme move detection

- Inputs: ordered daily bars with **close** (and dates).
- **return_pct** = (close\_event / close\_prev − 1) × 100, rounded consistently with other research features.
- **extreme_up** if return_pct ≥ **extreme_move_up_threshold_pct** (config, default see supplement).
- **extreme_down** if return_pct ≤ **−extreme_move_down_threshold_pct** (config; default symmetric).
- If neither: **no event** for that day.

### FR-2. Event classification

- Exactly one of the two types when an event fires; document tie-breaking if thresholds asymmetric.

### FR-3. Persistence (`ExtremeMoveEvent`)

New table (e.g. `extreme_move_events`), minimum fields:

| Field | Purpose |
|-------|---------|
| `id` | PK |
| `symbol` | Ticker (FK to `stocks.symbol` if consistent with 015) |
| `event_date` | Trading day of the extreme move |
| `return_pct` | Same-day return used for detection |
| `event_type` | `extreme_up` \| `extreme_down` |
| `created_at` | Insert time |

Optional MVP: `up_threshold_used`, `down_threshold_used` for audit.

**Unique constraint**: **(symbol, event_date)**.

### FR-4. Evaluation

- On-demand (or CLI-printed) aggregation from stored events + **`PriceDataRepository`**.
- Dimensions: **global**, **by_horizon**, **by_event_type**, **by_symbol** (as in 015 evaluation API shape).
- Reuse **`evaluable_count`** semantics when forward bars missing.

### FR-5. CLI

- **`backfill extreme-move`**: `--start`, `--end`, optional `--symbols`, optional `--replace-range`.
- **`evaluate extreme-move`**: date filters, **`--limit`** capped consistently with API (e.g. 2000).

### FR-6. API (read-only)

Prefix: **`/api/extreme-move`**

| Endpoint | Purpose |
|----------|---------|
| `GET .../events` | List/filter: symbol, since_date, until_date, event_type, pagination |
| `GET .../evaluation/summary` | Global + by_horizon + by_event_type |
| `GET .../evaluation/by-type` | Per-type aggregates |
| `GET .../evaluation/by-symbol` | Per-symbol aggregates; support **min_sample** like 015 |

### FR-7. Brownfield compatibility

- **Additive** SQLite migration via existing patterns (`Base.metadata.create_all` and/or `_migrate_*` if required).
- **No** changes to leader-follower or volume-spike tables beyond shared `price_data` / `stocks`.
- Services return **DTOs / dicts** at API boundary; follow **docs/ARCHITECTURE.md**.
- Tests: **unit** for pure return + threshold logic; **integration** for API with in-memory DB.

---

## Data requirements

- **Daily** OHLCV in **`price_data`** for symbols under study.
- **Universe**: same as existing backfill (e.g. all `stocks` or CLI `--symbols`).

---

## Risks

| Risk | Mitigation |
|------|------------|
| Threshold too high → too few events | Document defaults; config/env; report counts prominently |
| Threshold too low → noise | Checklist + median vs average; optional min close filter later |
| Meme names dominate | **by_symbol** breakdown; concentration checks per checklist |
| Confound with earnings / splits | MVP: document assumption (raw close); corporate actions out of scope |
| Sign flips across time splits | Require split evaluation before any 017+ work |

---

## Open questions

1. **Threshold levels**: single default **5%** vs **7%** vs **10%** per side—pick one default for v1, allow config for others without building a grid UI.
2. **Low-priced stocks**: exclude below **min_close** (config, default off) to reduce penny noise?
3. **Volatility normalization**: defer to post-MVP (e.g. return / trailing σ)—not in scope for first ship.
4. **Forward-return anchor**: confirm **event_date close** matches 015/007 for comparability (recommended default).
5. **Same bar as 015 overlap**: same stock/day could be both volume spike and extreme move—**do not merge** in MVP; cross-tabulation is manual/analyst.

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| 015 Volume spike | Template for **persistence**, **evaluation API shape**, **CLI**, **`since_date`/`until_date`**, **limit** semantics |
| 007 Leader-follower evaluation | Template for **horizons**, **`compute_forward_return`**, aggregates |
| `PriceDataRepository` | **Source of truth** for closes |
| `docs/SIGNAL_EVALUATION_CHECKLIST.md` | **Gate** before robustness/paper/optimization work |

---

## Requirements traceability (concise)

| ID | Requirement |
|----|-------------|
| FR-016-001 | Threshold-based daily extreme detection with configurable up/down magnitudes |
| FR-016-002 | Two-way event_type: extreme_up, extreme_down |
| FR-016-003 | Persist ExtremeMoveEvent with unique (symbol, event_date) |
| FR-016-004 | Forward returns 1d/3d/5d with aggregates by type and symbol |
| FR-016-005 | CLI backfill + evaluate |
| FR-016-006 | Read-only REST under `/api/extreme-move/*` |
| FR-016-007 | Tests + structured errors; no ML; no execution |

---

# Supplement: Recommended defaults (starting point only)

These are **not** implementation commitments until **plan.md** / **research.md** ratify them.

| Parameter | Recommended default | Notes |
|-----------|---------------------|--------|
| `extreme_move_up_threshold_pct` | **5.0** | Daily close-to-close % |
| `extreme_move_down_threshold_pct` | **5.0** | Symmetric magnitude |
| Evaluation horizons | **1, 3, 5** trading days | Match existing evaluation config style |
| Evaluation event `limit` (API/CLI max) | **2000** | Align with 015 |
| `min_close` filter | **0** (disabled) | Turn on only if penny noise appears |

**Mean-reversion read of metrics (analyst guidance, not coded rules):**

- After **`extreme_up`**, **negative** median forward return over 1d–3d supports short-horizon reversion **down**; flat or positive medians weaken the hypothesis.
- After **`extreme_down`**, **positive** median forward return supports reversion **up**.

Always pair with **checklist**: sample size, splits, concentration, median vs average.

---

# Supplement: Implementation plan guidance (for `/speckit.plan`, not part of this spec artifact)

When planning implementation (separate **plan.md** / **tasks.md** run):

1. **Model + table** `extreme_move_events` with unique **(symbol, event_date)**.
2. **Pure functions** module: `daily_return_pct(close_t, close_prev)`, `classify_extreme_move(return_pct, up_th, down_th) -> type | None`, easy to unit test.
3. **Repository** + **service**: `backfill_range`, `list_events`, `run_evaluation` / aggregate helpers (mirror **015** file layout where it reduces cognitive load).
4. **Evaluation**: reuse **`compute_forward_return`** from **`leader_follower_evaluation_service`**; duplicate only if a shared internal helper is extracted later.
5. **API router** `extreme_move.py`; register in **`main.py`**; mirror **015** query param naming (**`since_date`**, **`until_date`**, **`limit`**).
6. **CLI**: add commands under existing **`backfill`** and **`evaluate`** groups.
7. **Config**: `Settings` keys **`extreme_move_*`** (no magic numbers in services).
8. **Tests**: detection unit tests; evaluation aggregate tests; API integration tests; optional backfill idempotency test.
9. **ROADMAP**: add row when scope is approved (e.g. Phase 3 research task).

**Explicit non-actions for implementers:** no optimization CLI, no robustness grid, no paper sim until the **signal evaluation checklist** passes on a real DB slice.

---

## Document control

- **plan.md**, **tasks.md**, **research.md**, **data-model.md**, **contracts/**, **quickstart.md** are **out of scope** for this document iteration; run **`/speckit.plan`** and **`/speckit.tasks`** when ready.
- **No code** in this feature folder until tasks are approved.

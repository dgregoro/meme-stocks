# Hypothesis H2 — extreme down days and short-horizon mean reversion

**Status:** **Frozen (Step 1)** — **2026-03-30**; git tag **`h2-freeze-2026-03-30`** on the commit that records this freeze. Do not treat results as confirmatory until that tag exists locally (and is pushed if you rely on remote history).

**Last updated:** 2026-03-30

---

## Scope note (choosing this H2)

This file is filled out for **daily extreme moves** (spec **016** / **`extreme_move_events`**): large **down** days, forward returns over **trading-day** horizons **1, 3, 5**. It does **not** continue H1 (leader–follower / B1).

**Alternate lanes** you can swap in (replace hypothesis + procedure + freeze table):

| Lane | Idea | Primary CLI / service |
|------|------|------------------------|
| **S1** | Volume vs realized-vol mismatch | `evaluate daily-strategy s1-merit` (see `STRATEGY_TESTING_PLAN.md`) |
| **Volume spike** | `015` events + evaluation | `backfill` / `evaluate volume-spike` |
| **S7** | Rule discovery | `research` / gated search (complexity + OOS required) |

If you change lane, bump the title and **Step 1** tag name (e.g. `h2-s1-…`).

---

## Hypothesis (H2)

For symbols in the **study universe**, on **event days** where a **qualified extreme down** is detected under the **frozen** daily-return threshold (see snapshot), the symbol’s **forward simple return** from the **event-day close** over **K = 5** trading sessions is **strictly positive in expectation** on a **preregistered hold-out** calendar segment after subtracting **one** round-trip transaction cost at **`research_default_round_trip_cost_bps`** (same **percentage-point** convention as `research_execution.costs`).

**Secondary horizons:** **K ∈ {1, 3}** — reported for context only unless you elevate one to **co-primary** in the freeze (edit this sentence at Step 1).

**Direction:** **Extreme down** only (`event_type == extreme_down`) for this H2 wording; **extreme_up** is out of scope unless you fork a new hypothesis.

---

## Population, events, and horizon

| Element | Definition |
|---------|------------|
| **Universe** | Symbols present in **`stocks`** with sufficient **`price_data`** for forward **K** and backfill range (document actual list or “full seed universe” at Step 2). |
| **Event** | One row per (`symbol`, `event_date`) in **`extreme_move_events`** with `event_type = extreme_down`, produced by **`backfill extreme-move`** using frozen thresholds and volume-context rules (see config snapshot). |
| **Forward return** | Same convention as **`extreme_move_evaluation_service`**: `compute_forward_return` from **`event_date`**, **K** trading days, close-to-close **percent**. |
| **Net return (per event)** | `net_pct = gross_fwd_pct − round_trip_cost_pct`, with `round_trip_cost_pct = research_default_round_trip_cost_bps / 100` (identical to H1 / merit helpers). |
| **Primary K** | **5** trading days unless you freeze otherwise. |

---

## Baseline

**H2 primary null is not a matched calendar control** (that would be a follow-up, analogous to B1 for leader–follower):

- **Primary test:** Whether **mean (net forward return | extreme_down)** is **> 0** on the hold-out (one-sided economic null: “no bounce after large down”).
- **Optional later:** Add **matched non-event days** (same symbol, same weekday, no extreme event in window) as **H2b** with a separate freeze.

---

## Kill criteria (any one → kill H2 *as stated*)

1. **Underpowered:** Fewer than **80** evaluable **extreme_down** events in the **preregistered hold-out** segment (after `min_close` / price filters), and the gap cannot be closed without **loosening** frozen thresholds.
2. **No edge after costs (hold-out):** **Mean net** forward return at **primary K = 5** is **≤ 0**, or is **positive** but **&lt; 5 bps** per day in economically meaningful terms **and** not supported by stability checks (document how you map horizon return to “per day” in the Step 1 note).
3. **Brittle:** Predefined **rolling** or **multi-split** stability rule fails (e.g. **mean net** at **K** is **≤ 0** in a majority of preregistered splits, or sign flips without adequate N). *Define the exact split recipe at Step 1 (monthly rolling, merit-style `--splits`, etc.).*
4. **Timebox:** From the **recorded H2 freeze date**, **8 calendar weeks** pass without a documented decision (pass / kill / narrow) under this doc → record post-mortem and retire **this wording** of H2.

---

## Frozen configuration snapshot (fill at Step 1)

These must match **runtime** `Settings` at freeze (or list explicit overrides). *Do not change mid-H2 without a new freeze row.*

| Setting (Python field) | Value at freeze (draft defaults) |
|------------------------|----------------------------------|
| `extreme_move_up_threshold_pct` | **5.0** *(not used for H2 primary events)* |
| `extreme_move_down_threshold_pct` | **5.0** |
| `extreme_move_research_horizons` | **`"1,3,5"`** |
| `extreme_move_research_min_close` | **0.0** |
| `extreme_move_context_volume_high_ratio` | **1.5** |
| `extreme_move_context_volume_extreme_ratio` | **3.0** |
| `research_default_round_trip_cost_bps` | **10.0** |
| `volume_spike_research_baseline_window_days` | **20** *(rolling lookback for volume ratio; first **W** bars skipped per symbol)* |
| `volume_spike_research_baseline_statistic` | **median** |
| `volume_spike_research_min_baseline_volume` | **0.0** *(0 = disabled)* |

Volume context on each event uses **`compute_baseline_volume`** on the prior **W** volumes (`backend/app/services/extreme_move_service.py`, **`backfill_extreme_moves`**).

**Git:** Annotated tag **`h2-freeze-2026-03-30`** on the commit that records this table and hold-out dates.

### Preregistered stability (Step 7 — maps to kill §3 “Brittle”)

Train-only data: **`event_date` &lt; 2025-02-03** (same boundary as the hold-out table).

- **Splits:** **Calendar quarters** (Q1–Q4) with quarter bounds in **UTC calendar**; include only quarters whose **last day** is **before 2025-02-03**.
- **Estimator per quarter:** Mean **net** forward return at **K = 5** for **`extreme_down`** only, same definition as the primary test (`net_pct = gross_5d_pct − research_default_round_trip_cost_bps / 100`).
- **Sample rule:** Quarters with **evaluable `extreme_down` count &lt; 20** are **omitted** from the majority vote (not counted as failures).
- **Fail (“brittle”)** if, among quarters with **N ≥ 20**, **strict majority** have **mean net K=5 ≤ 0**.

(First time you run stability, log the quarter list, **N** per quarter, and means in **Step 7** or a research note—same discipline as H1 Step 6 logs.)

---

## Preregistered hold-out (fill before first outcome peek)

H2 uses the **same calendar segment as H1** (`docs/PRIMARY_HYPOTHESIS.md`) so hold-out results are directly comparable across hypotheses. **No peeping:** do not tune thresholds or filters using hold-out outcomes; complete **Step 1 freeze** (snapshot + tag) before evaluating this window.

| Field | Value |
|--------|--------|
| Hold-out **start** | **2025-02-03** (Monday) |
| Hold-out **end** | **2025-05-30** (Friday) |
| Train / tune boundary | All discretionary tuning uses only **event_date &lt; 2025-02-03** (and matching prices). |

---

## Operating procedure (steps)

1. **Freeze** — Complete the snapshot table and hold-out table above; commit; tag `h2-freeze-…`.
2. **Data** — `seed stocks` if needed; `backfill daily-prices --start … --end …` for universe; `backfill extreme-move --start … --end …` (see CLI `--help`). Log row counts: **`price_data`**, **`extreme_move_events`** for `extreme_down`.
3. **Treatment metrics** — `python3 -m backend.app.cli evaluate extreme-move --start 2025-02-03 --end 2025-05-30` (add filters as supported). Export or save JSON.
4. **Net returns** — Compute **mean net** at **K=5** from per-event forwards and **10 bps** cost (spreadsheet or small script); or extend evaluation service later with first-class **net** fields (out of scope unless you add it in a tracked commit).
5. **Costs** — Fixed **10 bps** round-trip unless freeze records an override.
6. **Hold-out** — Run evaluation **only** on the preregistered window; never tune that window’s dates to maximize metrics.
7. **Stability** — Run preregistered rolling / multi-split design (e.g. repeat evaluate on **train** slices only for exploratory work; hold-out remains untouched).
8. **Decide** — Table mapping § Kill criteria → evidence → **kill / continue / narrow** (same discipline as H1 Step 7).

### Step 2 run log (template)

| Step | Command / outcome |
|------|-------------------|
| Prices | No **`backfill daily-prices`** in this session — existing **`price_data`** spanned **2023-12-26 → 2025-12-31** (**31 878** rows, **63** symbols). |
| Events | **`backfill extreme-move --start 2023-12-26 --end 2025-12-31`** → **1 586** events upserted (**813** total **`extreme_down`** rows in DB after run). |
| Hold-out eval | **`evaluate extreme-move --start 2025-02-03 --end 2025-05-30 --limit 2000`** → **480** events in window (**275** **`extreme_down`**, **205** **`extreme_up`**) with full forward paths at **1/3/5**d. JSON: `data/research/h2_holdout_eval_2025-02-03_2025-05-30.json`. |

### Step 3–4 snapshot (gross CLI → net by hand)

Hold-out **`extreme_down`** only, **K = 5**, **`research_default_round_trip_cost_bps = 10`** ⇒ subtract **0.10** from reported **`avg_return_pct`** (same convention as merit / H1 helpers: **bps / 100** as percentage points).

| Metric | Value (this run, local DB) |
|--------|----------------------------|
| **N** (evaluable **5d**) | **275** |
| Mean **gross** **5d** | **+0.6086%** |
| Mean **net** **5d** | **+0.5086%** |

**Step 7** still required: map kill criteria, stability quarters, and explicit **pass / kill / narrow** — this table is **not** a final decision.

---

## References

- [`PURPOSE.md`](PURPOSE.md) — north star
- [`PRIMARY_HYPOTHESIS.md`](PRIMARY_HYPOTHESIS.md) — H1 (leader–follower); discipline template
- [`STRATEGY_EXPLORATION.md`](STRATEGY_EXPLORATION.md) — daily strategy IDs (S1–S7) if you pivot lanes
- [`STRATEGY_TESTING_PLAN.md`](STRATEGY_TESTING_PLAN.md) — sequence and tooling
- [`CAUSAL_RESEARCH.md`](CAUSAL_RESEARCH.md) — leakage and baseline hygiene
- [`STRATEGY_CONCLUSION_FRAMEWORK.md`](STRATEGY_CONCLUSION_FRAMEWORK.md) — hold-out policies
- Specs **016** / **017** under `specs/` — extreme-move context and evaluation notes

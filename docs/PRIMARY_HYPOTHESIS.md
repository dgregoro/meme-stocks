# Primary research hypothesis and baseline

**Status:** Operator commitment for the **leader–follower** lane. Aligns with [`PURPOSE.md`](PURPOSE.md) (hypothesis → measurable edge or kill → execution).

**Last updated:** April 3, 2026

---

## Hypothesis (H1)

For pre-defined **leader → follower** relationships evaluated under **frozen** leader-detection rules, when the leader has a **qualified leader event** on a given trading day, the **follower’s** forward return over the **frozen forward horizons** (trading sessions; see snapshot below) is **systematically different** from the baseline defined below, and that difference is **positive in expectation** on **hold-out** evaluation windows **after** applying a **conservative round-trip cost** (see snapshot: `research_default_round_trip_cost_bps`).

---

## Baseline (chosen): B1 — matched non-event days

**Decision:** Use **baseline B1** only. Do not switch to beta-adjusted market (B2) mid-study without explicitly revising this document.

**Definition:**

- **Event day (for the pair):** A trading day on which the **leader** satisfies a **qualified leader event** under the frozen detection configuration used for the test.
- **Non-event day (for the pair):** A trading day in the same evaluation window on which **no** such qualified leader event occurs for that leader (relative to the same rules and session semantics).
- **Matching:**
  1. **Day-of-week:** Non-event control days are restricted to the **same weekday** as the event day (e.g. event on Tuesday → compare only to follower outcomes on other **Tuesday** non-event days in the window, or to a pooled/set-matched control per the chosen estimator).
  2. **Regime (when available):** Where the evaluation pipeline defines a **shared regime label** for the follower (or market) on that day, control days must use the **same regime bucket** as the event day. If no regime series is available for a given run, matching is **DOW-only** until this doc is updated to require a regime feature.

**Excess (conceptual):** For each event, the quantity of interest is follower forward return at horizon **h** **minus** the corresponding baseline from matched non-event days (e.g. mean or matched-set average of follower forward returns on those days). Costs are applied **consistently** to both arms per the project’s research execution rules.

**Implementation note:** The codebase may not yet compute B1 end-to-end in one CLI; this file is the **preregistered** target. When implementing a metric, map explicitly to these definitions so results are comparable across runs.

---

## What the “8-week clock” means (and does not mean)

- **You do not wait 8 weeks of market time** to run a test. Historical evaluation uses already-stored (or backfilled) prices and signals; a multi-year backtest or walk-forward run can finish in **minutes to hours**.
- The **8-week timebox** is a limit on **your focused research calendar**: from the date you **record the rule freeze** (see below), you commit either to meet the preregistered minimum bar or to **kill** H1 as stated—so the project does not drift for months without a decision.
- **Optional later:** Live or **forward** paper trading does consume **wall-clock** time, but that is separate from “can I evaluate H1?” You evaluate H1 on **hold-out historical** windows first; forward testing is extra confirmation if you choose it.

**Example (for comparison):** Freeze **2026-04-03** → decision deadline **2026-05-29** (exactly **8 calendar weeks** / 56 days later). The **recorded** freeze for H1 is in the table below.

**Rule freeze record (Step 1 — recorded):**

| Field | Value |
|--------|--------|
| Freeze date (local) | **2026-04-03** |
| Decision deadline (freeze + 8 calendar weeks) | **2026-05-29** |
| Git snapshot | Git **`main`**; canonical pointer **`h1-freeze-2026-04-03`** (annotated tag on the commit that records this freeze). Use `git rev-parse h1-freeze-2026-04-03` for the exact SHA. |

**Important:** Values in the snapshot below are **`backend.app.config.Settings` defaults** as of that commit. Your **runtime** may differ if `deployment/.env` or the environment overrides any variable (Pydantic env names are typically **SCREAMING_SNAKE** for each field). Before Step 2, confirm effective settings match intent (or record overrides in a short note).

**`deployment/.env` check (2026-04-03):** The only leader-follower-related key is **`LEADER_FOLLOWER_DEBUG_MODE=false`**, which matches the frozen default (`leader_follower_debug_mode`). No other **`LEADER_*`**, **`FOLLOWER_*`**, **pair-filter**, or **`LEADER_FOLLOWER_EVALUATION_*`** overrides were present. Other entries in that file (paths, providers, credentials) do not change the H1 snapshot table; **never commit** real secrets to git.

---

## Frozen configuration snapshot (2026-04-03)

These fields define **qualified leader events**, cooldown, strength score, evaluation horizons, and optional pair filtering. Do **not** change them mid-H1 without bumping the freeze (new date, new doc section).

| Setting (Python field) | Default (frozen reference) | Notes |
|------------------------|----------------------------|--------|
| `leader_follower_enabled` | `False` | Scheduler/job gate; historical backfill can still generate signals via CLI. |
| `leader_return_threshold_pct` | `5.0` | Leader move threshold (%). |
| `leader_volume_spike_threshold` | `1.5` | Leader volume ratio vs baseline. |
| `follower_move_threshold_pct` | `3.0` | Used in detection pipeline for follower context. |
| `leader_follower_cooldown_days` | `1` | Days between repeat signals per pair. |
| `leader_follower_job_hour` | `17` | Scheduler hour (local semantics per deploy). |
| `leader_follower_strength_weight_return` | `0.6` | Strength score mix. |
| `leader_follower_strength_weight_volume` | `0.4` | Strength score mix. |
| `leader_follower_norm_return_cap_pct` | `15.0` | Cap for normalization. |
| `leader_follower_norm_volume_cap` | `4.0` | Cap for normalization. |
| `leader_follower_debug_mode` | `False` | If `True`, debug thresholds below apply. |
| `leader_return_threshold_pct_debug` | `3.0` | Only when debug mode on. |
| `leader_volume_spike_threshold_debug` | `1.2` | Only when debug mode on. |
| `leader_follower_evaluation_horizons` | `"1,3,5"` | **Frozen forward horizons (trading days)** for evaluation. |
| `leader_follower_evaluation_overlap_window_days` | `5` | Duplicate/overlap window for evaluation helpers. |
| `leader_follower_pair_min_signal_count` | `2` | Pair filter / ranking (009). |
| `leader_follower_pair_min_avg_return_1d` | `0.0` | Pair filter. |
| `leader_follower_pair_min_win_rate_1d` | `0.5` | Pair filter. |
| `enable_pair_filtering_for_signals` | `False` | If `True`, signal generation restricts to passing pairs. |
| `leader_follower_pair_filter_lookback_days` | `90` | Lookback when filtering pairs for signals. |
| `leader_follower_optimization_max_grid_points` | `256` | Walk-forward grid cap (research CLI). |
| `leader_follower_robustness_max_evaluations` | `5000` | Robustness cap (research CLI). |
| `leader_follower_regime_backfill_symbols` | `"SPY"` | Regime-gate backfill universe hint. |
| `research_default_round_trip_cost_bps` | `10.0` | Reference round-trip for research / cost alignment. |

**Pair / group universe:** Candidate **leader → follower** pairs come from seeded **`stocks` / `stock_groups`** and the leader-follower candidate pipeline in code—not from a single env string. When you run backfills, note **which symbols exist in DB** at that run; that is part of the empirical “universe” for H1.

---

## Kill criteria (any one → kill H1 *as stated*)

1. **Underpowered:** After bounded data effort, fewer than **50** usable event evaluations per primary hold-out segment **or** fewer than **40** completed paper outcomes on validated pairs—and the gap cannot be closed without loosening frozen rules.
2. **No edge after costs (hold-out):** Mean **net** excess vs B1 is **zero or negative** at the primary horizon, or edge is **under 5 bps** per day-equivalent and not supported by sample size / stability.
3. **Brittle:** Walk-forward / rolling stability fails in the project gates (e.g. excess sign unstable across most splits).
4. **Timebox:** From the **recorded freeze date**, **8 calendar weeks** pass without meeting the preregistered minimum (e.g. hold-out mean net excess is **positive** and stability pass on **≥ 2 of 3** rolling configurations) → stop and record a short post-mortem. This is **not** a requirement to idle; it is a **deadline to decide** after serious effort (including historical runs).

---

## Operating procedure (steps)

Follow in order; do not treat “event-only” aggregates as a full H1 test until **B1 excess** exists.

1. **Freeze the experiment** ✅ **Recorded 2026-04-03** (rule-freeze table + configuration snapshot). Annotated tag **`h1-freeze-2026-04-03`** created on the freeze commit.

2. **Data and signals**  
   Ensure stocks and OHLCV exist for all leaders/followers. Build `leader_follower_signal` rows over your study window (e.g. `python -m backend.app.cli backfill leader-follower` with dates from `--help`). Until you have enough events, you are in the “underpowered” branch of the kill criteria—that is a valid outcome.

3. **Event-arm metrics (existing code)**  
   Use `run_evaluation` / `aggregate_by_pair` in `leader_follower_evaluation_service` for **event-day** follower forward returns. This is the **treatment** arm only—not yet excess vs B1.

4. **Baseline B1 (required for H1)**  
   For each event, compute follower forward return on the event day vs the baseline from **matched non-event** days (same DOW; same regime when defined). Implement as a script, notebook, or service helper with tests; until this exists, **do not** claim H1 is tested.

5. **Costs and execution read**  
   Apply the **same** round-trip cost assumption as in research defaults (and align with paper sim if you use it: `python -m backend.app.cli simulate leader-follower`, verifying `--cost_pct` units in `--help`). Compare **net** excess vs B1 on **hold-out** only for the main decision.

6. **Hold-out and stability**  
   Use strict time splits (train / validate / test or rolling windows). Tune only on train; **report** validate/test. Use walk-forward / robustness CLIs where they match this study (`optimize leader-follower`, `robustness leader-follower` — see `--help`).

7. **Decide**  
   Apply the kill criteria above. **Kill** means this **wording** of H1 is retired (document why), not that the whole repository is abandoned.

---

## References

- [`PURPOSE.md`](PURPOSE.md) — north star
- [`CAUSAL_RESEARCH.md`](CAUSAL_RESEARCH.md) — leakage and alignment hygiene (replace “Reddit” mentally with price-only controls where relevant)

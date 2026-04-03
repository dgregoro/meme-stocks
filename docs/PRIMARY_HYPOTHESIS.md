# Primary research hypothesis and baseline (H1 — leader–follower)

**Status:** **H1 / leader–follower lane — closed for new primary preregistration** (2026-04-03). Step 7 outcome recorded below; retain this file for audit and replication. **New work:** preregister in **[`H2_HYPOTHESIS.md`](H2_HYPOTHESIS.md)** (or rename once H2 is drafted), then freeze there.

Aligns with [`PURPOSE.md`](PURPOSE.md) (hypothesis → measurable edge or kill → execution). **Step 7 (2026-04-03):** **Do not kill** H1 on **B1 hold-out mean** net excess (§93); **stability / execution** evidence (§95–§94) is **mixed** — see Step 7 log.

**Last updated:** 2026-04-03 (H1 closure note; Step 7 decision log; hold-out + Steps 5–6; Steps 2–3 below)

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


| Field                                         | Value                                                                                                                                                                            |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Freeze date (local)                           | **2026-04-03**                                                                                                                                                                   |
| Decision deadline (freeze + 8 calendar weeks) | **2026-05-29**                                                                                                                                                                   |
| Git snapshot                                  | Git `**main`**; canonical pointer `**h1-freeze-2026-04-03**` (annotated tag on the commit that records this freeze). Use `git rev-parse h1-freeze-2026-04-03` for the exact SHA. |


**Important:** Values in the snapshot below are `**backend.app.config.Settings` defaults** as of that commit. Your **runtime** may differ if `deployment/.env` or the environment overrides any variable (Pydantic env names are typically **SCREAMING_SNAKE** for each field). Before Step 2, confirm effective settings match intent (or record overrides in a short note).

`**deployment/.env` check (2026-04-03):** The only leader-follower-related key is `**LEADER_FOLLOWER_DEBUG_MODE=false`**, which matches the frozen default (`leader_follower_debug_mode`). No other `**LEADER_***`, `**FOLLOWER_***`, **pair-filter**, or `**LEADER_FOLLOWER_EVALUATION_*`** overrides were present. Other entries in that file (paths, providers, credentials) do not change the H1 snapshot table; **never commit** real secrets to git.

---

## Frozen configuration snapshot (2026-04-03)

These fields define **qualified leader events**, cooldown, strength score, evaluation horizons, and optional pair filtering. Do **not** change them mid-H1 without bumping the freeze (new date, new doc section).


| Setting (Python field)                           | Default (frozen reference) | Notes                                                                       |
| ------------------------------------------------ | -------------------------- | --------------------------------------------------------------------------- |
| `leader_follower_enabled`                        | `False`                    | Scheduler/job gate; historical backfill can still generate signals via CLI. |
| `leader_return_threshold_pct`                    | `5.0`                      | Leader move threshold (%).                                                  |
| `leader_volume_spike_threshold`                  | `1.5`                      | Leader volume ratio vs baseline.                                            |
| `follower_move_threshold_pct`                    | `3.0`                      | Used in detection pipeline for follower context.                            |
| `leader_follower_cooldown_days`                  | `1`                        | Days between repeat signals per pair.                                       |
| `leader_follower_job_hour`                       | `17`                       | Scheduler hour (local semantics per deploy).                                |
| `leader_follower_strength_weight_return`         | `0.6`                      | Strength score mix.                                                         |
| `leader_follower_strength_weight_volume`         | `0.4`                      | Strength score mix.                                                         |
| `leader_follower_norm_return_cap_pct`            | `15.0`                     | Cap for normalization.                                                      |
| `leader_follower_norm_volume_cap`                | `4.0`                      | Cap for normalization.                                                      |
| `leader_follower_debug_mode`                     | `False`                    | If `True`, debug thresholds below apply.                                    |
| `leader_return_threshold_pct_debug`              | `3.0`                      | Only when debug mode on.                                                    |
| `leader_volume_spike_threshold_debug`            | `1.2`                      | Only when debug mode on.                                                    |
| `leader_follower_evaluation_horizons`            | `"1,3,5"`                  | **Frozen forward horizons (trading days)** for evaluation.                  |
| `leader_follower_evaluation_overlap_window_days` | `5`                        | Duplicate/overlap window for evaluation helpers.                            |
| `leader_follower_pair_min_signal_count`          | `2`                        | Pair filter / ranking (009).                                                |
| `leader_follower_pair_min_avg_return_1d`         | `0.0`                      | Pair filter.                                                                |
| `leader_follower_pair_min_win_rate_1d`           | `0.5`                      | Pair filter.                                                                |
| `enable_pair_filtering_for_signals`              | `False`                    | If `True`, signal generation restricts to passing pairs.                    |
| `leader_follower_pair_filter_lookback_days`      | `90`                       | Lookback when filtering pairs for signals.                                  |
| `leader_follower_optimization_max_grid_points`   | `256`                      | Walk-forward grid cap (research CLI).                                       |
| `leader_follower_robustness_max_evaluations`     | `5000`                     | Robustness cap (research CLI).                                              |
| `leader_follower_regime_backfill_symbols`        | `"SPY"`                    | Regime-gate backfill universe hint.                                         |
| `research_default_round_trip_cost_bps`           | `10.0`                     | Reference round-trip for research / cost alignment.                         |


**Pair / group universe:** Candidate **leader → follower** pairs come from seeded `**stocks` / `stock_groups`** and the leader-follower candidate pipeline in code—not from a single env string. When you run backfills, note **which symbols exist in DB** at that run; that is part of the empirical “universe” for H1.

---

## Kill criteria (any one → kill H1 *as stated*)

1. **Underpowered:** After bounded data effort, fewer than **50** usable event evaluations per primary hold-out segment **or** fewer than **40** completed paper outcomes on validated pairs—and the gap cannot be closed without loosening frozen rules.
2. **No edge after costs (hold-out):** Mean **net** excess vs B1 is **zero or negative** at the primary horizon, or edge is **under 5 bps** per day-equivalent and not supported by sample size / stability.
3. **Brittle:** Walk-forward / rolling stability fails in the project gates (e.g. excess sign unstable across most splits).
4. **Timebox:** From the **recorded freeze date**, **8 calendar weeks** pass without meeting the preregistered minimum (e.g. hold-out mean net excess is **positive** and stability pass on **≥ 2 of 3** rolling configurations) → stop and record a short post-mortem. This is **not** a requirement to idle; it is a **deadline to decide** after serious effort (including historical runs).

---

## Operating procedure (steps)

Follow in order; do not treat “event-only” aggregates as a full H1 test until **B1 excess** exists.

1. **Freeze the experiment** ✅ **Recorded 2026-04-03** (rule-freeze table + configuration snapshot). Annotated tag `**h1-freeze-2026-04-03`** created on the freeze commit.
2. **Data and signals** ✅ **Completed 2026-04-03** for the window below (see **Step 2 run log**).
  Ensure stocks and OHLCV exist for all leaders/followers. Persist signals in `**leader_follower_signals`** over your study window (`python -m backend.app.cli backfill leader-follower --start … --end …`). `seed stocks` and `seed stock-groups` must be run first so the group universe is non-empty. Until you have enough events, you are in the “underpowered” branch of the kill criteria—that is a valid outcome.

### Step 2 run log (environment: `deployment/.env`, `DATABASE_URL=sqlite:///./data/app.db`)


| Step   | Command / outcome                                                                                                                                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Seed   | `seed stocks` → 63 symbols; `seed stock-groups` → groups populated                                                                                                                                  |
| Prices | `backfill daily-prices --start 2024-01-02 --end 2025-12-31` → **31,878** `price_data` rows, 63 symbols                                                                                              |
| Replay | `backfill leader-follower --start 2024-01-02 --end 2025-12-31` → **522** trading days processed, **0** skipped, **5,692** signals, **835** leader events; signal dates **2024-01-02 .. 2025-12-19** |


**Note:** An earlier attempt through 2026-03-27 hit API/DB errors (`Failed to list price data`, `Failed to get all symbols from stock groups`) after the local DB had no `**stocks`** rows; re-running `**seed stocks**` then prices then replay produced a clean result. Revisit **2026** bars later if you extend the calendar window.

1. **Event-arm metrics (existing code)** ✅ **CLI recorded 2026-04-03** (`evaluate leader-follower-aggregates`; see Step 3 log).
  Use `run_evaluation` / `aggregate_by_pair` (or the CLI below) for **event-day** follower forward returns. This is the **treatment** arm only—not yet excess vs B1.

### Step 3 run log (same DB / window as Step 2)


| Field                             | Value                                                                                                                                         |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Command                           | `python -m backend.app.cli evaluate leader-follower-aggregates --start 2024-01-02 --end 2025-12-31` (omit `--limit` for all signals in range) |
| Signals                           | **5,692**                                                                                                                                     |
| Distinct (leader, follower) pairs | **767**                                                                                                                                       |
| Horizons                          | **1, 3, 5** (trading days; from `leader_follower_evaluation_horizons`)                                                                        |


Full JSON includes per-pair `signal_count`, `1d` / `3d` / `5d` **win_rate** and **avg_return_pct** (treatment only).

1. **Baseline B1 (required for H1)** ✅ **Service + CLI 2026-03-30** (DOW-only matching until regime is wired).
  For each event, compute follower forward return on the event day vs the baseline from **matched non-event** days (same DOW; same regime when defined). Implemented as `build_b1_excess_pair_aggregates` in `backend/app/services/leader_follower_evaluation_service.py` with tests; **do not** claim full H1 pass until hold-out (steps 5–6) is run the same way.

### Step 4 implementation (reference)


| Piece                 | Location                                                                                                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Control pool + excess | `collect_b1_control_returns`, `build_b1_excess_pair_aggregates`                                                                                                                |
| CLI (JSON)            | `python -m backend.app.cli evaluate leader-follower-b1 --start YYYY-MM-DD --end YYYY-MM-DD` (same filters as Step 3: `--leader`, `--follower`, omit `--limit` for all signals) |
| Tests                 | `backend/tests/test_leader_follower_evaluation_service.py`                                                                                                                     |


**Note:** JSON includes both **gross** and **net** arms (Step 5). With **symmetric** one round-trip on event and baseline mean, **net excess equals gross excess**; net event and net baseline still document the execution read.

1. **Costs and execution read** ✅ **Service + CLI 2026-03-30**
  Apply the **same** round-trip cost assumption as in research defaults (`research_default_round_trip_cost_bps`, surfaced as `costs.round_trip_cost_pct` — matches `simulate leader-follower --cost_pct` in **percentage points**). Compare **net** excess vs B1 on the **preregistered hold-out** window below; pass that window as `--start` / `--end` and add `--holdout` to tag JSON metadata only.

### Preregistered primary hold-out (H1) — **locked**

Envelope adjusted from an initial Feb–Jun 2025 intent so **calendar endpoints are a Monday and a Friday** (inclusive filter uses `signal_date`; trading days only carry data).


| Field                                | Value                                                                                                                                                                                                                               |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hold-out start (Monday)**          | **2025-02-03**                                                                                                                                                                                                                      |
| **Hold-out end (Friday)**            | **2025-05-30**                                                                                                                                                                                                                      |
| Rationale                            | First Monday on/after 2025-02-01; last Friday on/before 2025-06-01.                                                                                                                                                                 |
| **Train / tune boundary**            | Use only **signal_date 2025-02-03** (and matching prices) for any parameter tuning or pair selection **before** reporting this hold-out.                                                                                            |
| Empirical note (current DB, 2026-04) | Inclusive signal filter over this envelope: **948** `leader_follower_signals`; observed span **2025-02-04** … **2025-05-30** (first row may fall after the Monday if a session had no qualified events). Re-count after any replay. |


**Freeze:** Do **not** change these dates to improve ex-post fit. A new hypothesis requires a new freeze / section.

### Step 5 implementation (reference)


| Piece      | Location                                                                                                                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Net fields | `build_b1_excess_pair_aggregates` — `avg_net_event_return_pct`, `avg_net_baseline_mean_pct`, `avg_net_excess_pct`, pair-level mirrors |
| Cost model | `backend/app/services/research_execution/costs.py` (same as merit / backtest helpers)                                                 |
| CLI        | `evaluate leader-follower-b1` … `--round-trip-cost-bps` (override), `--holdout` (sets `evaluation_context.window_role`)               |


### Step 5 run log (hold-out evaluation recorded)


| Field                             | Value                                                                                                                                                                         |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Run recorded                      | **2026-04-03** (local CLI; DB as of that run)                                                                                                                                 |
| Hold-out dates                    | **2025-02-03** (Mon) … **2025-05-30** (Fri) — see **Preregistered primary hold-out**                                                                                          |
| Command                           | `python3 -m backend.app.cli evaluate leader-follower-b1 --start 2025-02-03 --end 2025-05-30 --holdout`                                                                        |
| Signals (loaded)                  | **948**                                                                                                                                                                       |
| Distinct (leader, follower) pairs | **467**                                                                                                                                                                       |
| Cost                              | **10** bps round-trip (default); `avg_net_excess_pct` = `avg_excess_pct` (symmetric)                                                                                          |
| **1d**                            | evaluable **948**; **avg_net_excess_pct** **+0.2209**; median **+0.4595**; skips **0**                                                                                        |
| **3d**                            | evaluable **948**; **avg_net_excess_pct** **+0.2380**; median **-0.0330**; skips **0**                                                                                        |
| **5d**                            | evaluable **948**; **avg_net_excess_pct** **+0.8503**; median **+0.5515**; skips **0**                                                                                        |
| Full JSON                         | Repo root `lf_b1_holdout_2025-02-03_2025-05-30.json` (matches gitignore `lf_*.json`; keep or copy if you need it in version control)                                          |
| Primary horizon vs kill §90       | H1 does not designate a single primary horizon here; **all three** horizons show **positive** mean net excess on this hold-out (see kill text for 5 bps / stability caveats). |
| Paper sim cross-check             | Optional: `simulate leader-follower` with `--cost_pct` `0.1`                                                                                                                  |


1. **Hold-out and stability** ✅ **Rolling paper robustness recorded 2026-04-03** (below).
  Use strict time splits (train / validate / test or rolling windows). **Primary** H1 **B1** hold-out: **2025-02-03 … 2025-05-30** (Step 5). Tune only on data **before** 2025-02-03 for any discretionary tuning. **Rolling** evaluation here uses the `**robustness leader-follower`** CLI (paper-trading metrics), which is **not** the same estimator as B1 close-to-close excess—report both separately. Optional: `**optimize leader-follower`** for train/validate grid search (`--help`).

### Step 6 run log (rolling robustness — paper trading)


| Field                                     | Value                                                                                                                                                                                                                                                          |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Command                                   | `python3 -m backend.app.cli robustness leader-follower --overall-start 2024-01-02 --overall-end 2025-05-30 --train-window-months 6 --validate-window-months 2 --step-months 2 --candidates-file data/research/h1_step6_rolling_robustness_default_config.json` |
| Overall range                             | **2024-01-02** … **2025-05-30** (ends with preregistered hold-out month; no post–May 2025 bars in this run)                                                                                                                                                    |
| Windows                                   | Train **6** calendar months, validate **2**, step **2**, optional test **off**                                                                                                                                                                                 |
| Candidate file                            | `data/research/h1_step6_rolling_robustness_default_config.json` — single candidate: `next_open`, `fixed_days`, `holding_days` **3**, `max_positions_per_event` **2**, `per_trade_cost_pct` **0.1**                                                             |
| Splits                                    | **5**                                                                                                                                                                                                                                                          |
| Persisted run                             | DB `leader_follower_robustness_runs.id` = **1**                                                                                                                                                                                                                |
| `frac_positive_validation`                | **0.40** (**2** of **5** splits with **positive** validation cumulative return %)                                                                                                                                                                              |
| `validation_positive_sign_by_split`       | **F, T, F, F, T** (split index order)                                                                                                                                                                                                                          |
| Validation cumulative return % (by split) | **-87.57**, **+96.07**, **-45.94**, **-87.08**, **+131.16**                                                                                                                                                                                                    |
| Median validation cumulative return %     | **-45.94** (aggregate JSON on rank-1 row)                                                                                                                                                                                                                      |
| Ineligible splits (trades < min)          | **0**                                                                                                                                                                                                                                                          |


**Read with Step 5:** Fixed-window **B1** hold-out shows **positive** mean net excess on 1d/3d/5d. Rolling **paper** validation is **volatile** and **median-negative** for this default sim config—do not treat as the same gate as B1 without aligning assumptions (entry/exit, horizons vs `holding_days`). Kill **§95** (brittle) and timebox **§94** refer to stability language you should map explicitly (e.g. fraction of splits positive vs a preregistered rule).

1. **Decide** ✅ **Recorded 2026-04-03** (operator review log below).
  Apply the kill criteria above. **Kill** means this **wording** of H1 is retired (document why), not that the whole repository is abandoned.

### Step 7 decision log (kill criteria → evidence)

Decision date: **2026-04-03** (same calendar day as rule freeze; decision deadline for the 8-week timebox remains **2026-05-29** per §36).


| Criterion                  | Trigger if…                                                                                                                                                                 | Evidence (this study)                                                                                                                                                                                                                                        | Outcome                                                                                                                                                                                                        |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **§92 Underpowered**       | < **50** usable hold-out evaluations **or** < **40** completed paper outcomes on validated pairs (and cannot fix without defrosting).                                       | Hold-out **948** signals with full B1 evaluability (Step 5).                                                                                                                                                                                                 | **Not triggered**                                                                                                                                                                                              |
| **§93 No edge (hold-out)** | Mean **net** excess vs B1 ≤ **0** at primary horizon, **or** edge < **5 bps** (day-equivalent) without support.                                                             | Mean **avg_net_excess_pct** **+0.2209** (1d), **+0.2380** (3d), **+0.8503** (5d) — all **positive** and ≫ **0.05%** (5 bps). Median 3d slightly negative (Step 5).                                                                                           | **Not triggered** on **mean** at any horizon; monitor **median / dispersion** in any revision of H1.                                                                                                           |
| **§95 Brittle**            | Rolling / walk-forward stability **fails** (e.g. sign unstable across **most** splits).                                                                                     | Step 6 **paper** robustness: **3**/5 validation splits **negative** cumulative return, **2**/5 **positive**; median validation return **negative**. **Rolling B1 excess** was **not** run — §95 cannot yet be applied to **B1** splits.                      | **Triggered** for **default paper-trading** stability as run. **Not** automatically a kill for the **B1-only** claim in H1 unless you adopt §95 for that estimator too.                                        |
| **§94 Timebox**            | **8** calendar weeks after freeze **without** meeting preregistered minimum (example text: positive hold-out excess **and** stability **≥ 2 of 3** rolling configurations). | Hold-out mean excess **positive** (above). Rolling example in §94 is **not** the same as Step 6’s **5** splits × **1** config (40% positive); **no** prewritten “2 of 3 configurations” grid was run. As of **2026-04-03**, the **deadline has not passed**. | **Not triggered** by calendar; **compound “minimum bar”** (edge + stability) is **not** fully demonstrated under a strict read—treat as **follow-up** (rolling B1, clearer stability rule, or revised prereg). |


**Summary judgment**

- **H1 as stated (B1, preregistered hold-out, mean net excess after costs):** **Do not kill** on §92–§93 with the current numbers.
- **Execution / paper-trading story and generic “stability”:** **Weak** on Step 6 defaults (§95 for that gate). Do **not** treat as validated for sizing or automation without aligning sim to B1 or improving stability.
- **Next actions (optional):** (1) Preregister a **rolling B1** or stability rule tied to **B1** sign/ mean. (2) Re-run **robustness** with configs closer to evaluation (e.g. `same_close`, `holding_days` matching horizons). (3) Before **2026-05-29**, either meet an explicit stability bar you write down or **kill / narrow** the claim under §94 discipline.

Operator may **revise** this log only by adding a dated entry (new freeze, new hypothesis, or explicit reversal)—not by editing past rows to match ex-post preferences.

---

## References

- `[PURPOSE.md](PURPOSE.md)` — north star
- `[CAUSAL_RESEARCH.md](CAUSAL_RESEARCH.md)` — leakage and alignment hygiene (replace “Reddit” mentally with price-only controls where relevant)

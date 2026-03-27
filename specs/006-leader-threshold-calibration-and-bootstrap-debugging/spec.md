# Feature Specification: Leader Threshold Calibration and Bootstrap Debugging

**Feature Name**: leader-threshold-calibration-and-bootstrap-debugging
**Feature Branch**: `006-leader-threshold-calibration-and-bootstrap-debugging`
**Created**: 2026-03-22
**Status**: Draft
**ROADMAP**: Phase 3/4 bootstrap-phase alignment (follows 005-grouped-leader-universe)
**Input**: Make leader detection inspectable and tunable so the pipeline can produce meaningful intermediate outputs during bootstrap.

---

## Context

- **Brownfield repo**: Leader-follower detection is implemented and running
- **stock_groups** is populated; leader detection is restricted to the grouped universe (005)
- **Observed state (post-005)**:
  - `grouped_leader_universe_size` > 0
  - `leader_events_detected` = 0
  - `empty_reason` = `"no_leaders"`
- **Interpretation**: Thresholds or criteria are too strict (or misaligned with data) for the grouped universe

**Important framing**: This is not about new trading strategies. It is about making the system **inspectable and tunable** — understanding *why* symbols do not qualify as leaders and supporting calibration during bootstrap.

---

## Problem Statement

- Leader detection currently produces zero leaders in the grouped universe under default thresholds
- The system does not expose enough information to understand why symbols are rejected
- Without visibility into near-misses and rejection reasons, calibration is guesswork
- We need structured observability and controlled threshold adjustment to progress

---

## Goals

- Make leader detection explainable at the symbol level
- Surface near-miss candidates for debugging
- Enable controlled threshold relaxation in bootstrap/debug mode
- Support inspection across multiple recent runs
- Keep changes minimal and compatible with existing architecture

---

## Non-Goals

- No changes to follower selection or confirmation logic
- No expansion to full-market leader detection
- No ML or statistical learning of thresholds
- No broad UI work beyond minimal API support
- No sentiment or new data sources
- No learned relationship modeling
- No major schema redesign

---

## User Stories

### User Story 1: Understand why no leaders were detected

As a developer,
I want to see which grouped symbols were evaluated and why they failed leader criteria,
so that I can debug and calibrate thresholds.

**Acceptance criteria:**
- For a given run, API can return evaluated symbols with:
  - `return_pct` (or equivalent metric)
  - `volume_ratio`
  - `leader_score` (if applicable)
  - `qualified_as_leader` (boolean)
  - `rejection_reasons` (structured list)
- Rejection reasons must be explicit (e.g., `below_return_threshold`, `insufficient_volume`, `missing_data`)

---

### User Story 2: Inspect near-miss leaders

As a developer,
I want to see the top symbols that almost qualified as leaders,
so that I can determine whether thresholds are too strict.

**Acceptance criteria:**
- API returns top N symbols ranked by leader score or return
- Includes symbols that did not qualify but were closest
- Includes relevant metrics used in decision

---

### User Story 3: Enable bootstrap/debug mode for leader thresholds

As a developer,
I want to run the pipeline with slightly relaxed thresholds,
so that I can validate downstream stages (candidate selection, signals).

**Acceptance criteria:**
- Configurable mode (e.g., env or config flag) for bootstrap/debug
- Allows adjusting:
  - return threshold
  - volume threshold
  - other leader criteria if applicable
- Diagnostics clearly indicate when debug mode is active

---

### User Story 4: Inspect leader detection across multiple runs

As a developer,
I want to view leader detection results across recent runs,
so that I can determine if "no_leaders" is persistent or occasional.

**Acceptance criteria:**
- API supports querying runs over a time range
- Provides summary per run:
  - grouped universe size
  - leaders detected
  - near-miss count
- Supports identifying patterns over time

---

### User Story 5: Preserve clean diagnostics

As a developer,
I want structured `empty_reason` and diagnostics to remain consistent,
so that I can track pipeline state across runs.

**Acceptance criteria:**
- `empty_reason` remains consistent and meaningful
- New reasons (if added) are well-defined and non-overlapping
- Diagnostics remain machine-readable

---

## Functional Requirements

### 1. Symbol-level evaluation output

- For each run, capture or compute evaluation data for grouped symbols:
  - return metrics (`return_pct`, `prev_close`, `curr_close`)
  - volume metrics (`volume_ratio`, `avg_volume`, `curr_volume`)
  - leader qualification result (boolean)
  - rejection reasons (list from taxonomy)
- Must be accessible via API

### 2. Rejection reason taxonomy

Define a small, explicit set of reasons. Do not use vague free-text.

| Reason | When Used |
|--------|-----------|
| `insufficient_bars` | Fewer than MIN_BARS_FOR_LEADER (5) bars |
| `no_data_on_event_date` | Last bar date ≠ event_date |
| `zero_avg_volume` | avg_volume <= 0 |
| `below_return_threshold` | abs(return_pct) < threshold |
| `insufficient_volume` | volume_ratio < threshold |
| `error` | Exception during evaluation (include context if safe) |

### 3. Near-miss ranking

- Rank symbols by proximity to qualifying as leader
- Deterministic and explainable
- Suggested proxy: `min(abs(return_pct) - return_threshold, 0)² + min(volume_ratio - vol_threshold, 0)²` — symbols that failed by smallest margin rank highest
- Alternative: rank by `abs(return_pct)` for return-failures, by `volume_ratio` for volume-failures

### 4. Bootstrap/debug mode

- Configurable via environment or config (e.g., `LEADER_FOLLOWER_DEBUG_MODE=true` or `LEADER_FOLLOWER_BOOTSTRAP_MODE=true`)
- When enabled, uses alternate threshold values (e.g., lower return/volume thresholds)
- Must be clearly visible in run metrics/diagnostics (e.g., `debug_mode: true` in metrics)
- Does not change core detection logic — only thresholds

### 5. Multi-run aggregation

- Ability to query recent runs and see leader detection outcomes
- Minimal aggregation sufficient for debugging (not a full analytics system)
- Per-run summary: `grouped_leader_universe_size`, `leader_events_detected`, `near_miss_count`

### 6. API endpoints

| Endpoint | Purpose | Parameters | Response shape |
|----------|---------|------------|----------------|
| `GET /api/leader-follower/leader-debug` | Symbol-level evaluation for a run | `run_id` (required), `limit` (optional, default 50) | List of evaluated symbols with metrics and rejection_reasons |
| `GET /api/leader-follower/leader-near-miss` | Top near-miss symbols for a run | `run_id` (required), `limit` (optional, default 20) | List of near-miss symbols ranked by proximity to qualifying |
| `GET /api/leader-follower/runs` (extend existing) | Runs with optional date filter | `since_date`, `until_date`, `limit` | Existing shape + optional `near_miss_count` per run when available |

**Empty-state behavior:**
- `leader-debug`: If run has no debug data, return 404 or empty list with clear message
- `leader-near-miss`: If run has no near-miss data, return empty list

### 7. Brownfield constraints

- Minimal schema changes; prefer computed outputs where possible
- Reuse `job_run_history` and `leader_events`; avoid storing large per-symbol datasets unless necessary
- If debug data must be persisted, use a lightweight table (e.g., `leader_debug_evaluations` with run_id, symbol, metrics_json, rejection_reasons) or embed in run metrics
- Keep performance reasonable (avoid N+1 or heavy aggregation on large universes)

---

## Data Requirements

- **Existing**: price/volume data (`price_data`), `leader_events`, `job_run_history` with `metrics_json`
- **Optional**: Lightweight persistence for debug data if computed-on-demand is too expensive or we need historical replay

---

## Current Implementation Reference

Leader detection in `backend/app/services/leader_follower_service.py`:

- Iterates over grouped symbols from `stock_group_repo.get_all_symbols()`
- For each symbol: fetches bars, requires 5 bars, last bar on event_date
- Computes `return_pct`, `volume_ratio`
- Rejects if `abs(return_pct) < leader_return_threshold_pct` (default 5.0)
- Rejects if `volume_ratio < leader_volume_spike_threshold` (default 1.5)
- On exception: logs and continues; symbol not surfaced
- **No structured rejection reasons; no near-miss output**

Config in `backend/app/config.py`:
- `leader_return_threshold_pct`: 5.0
- `leader_volume_spike_threshold`: 1.5

---

## Risks / Tradeoffs

| Risk | Mitigation |
|------|-------------|
| Increased verbosity vs performance | Compute on demand or store only when debug mode enabled |
| Storing vs computing debug data on demand | Start with compute-on-request; persist only if needed |
| Overfitting thresholds during bootstrap | Document debug mode as temporary; keep production thresholds conservative |
| Confusion between debug mode and production | Always expose `debug_mode` flag in metrics/diagnostics |

---

## Open Questions

1. **Persist vs compute**: Should debug data be persisted (new table or metrics_json extension) or computed on request? Computed is simpler but may require re-running detection logic.
2. **Near-miss count**: How many symbols in near-miss output? Default 20; configurable?
3. **Debug mode scope**: Per-run override or global config? Global config (env) is simpler; per-run would require passing params through job invocation.
4. **Metrics_json size**: Embedding per-symbol evaluations in metrics_json could bloat it. Prefer separate persistence or on-demand computation.

---

## Out of Scope (Explicit)

- Changing follower candidate logic
- Adding sentiment or new data sources
- Learned relationship modeling
- Major schema redesign
- UI dashboards beyond minimal API support

---

# Appendix: Recommended MVP Implementation Approach

## Phased approach

1. **Phase A: Rejection reasons and in-run collection**
   - Modify `detect_leaders` to collect evaluation records (symbol, return_pct, volume_ratio, qualified, rejection_reasons) in memory during the run
   - Extend run metrics to include `near_miss_count` and optionally a summary of rejection reason distribution
   - Store evaluation data: either in a new `leader_debug_evaluations` table keyed by run_id, or in an extended metrics blob — prefer table for queryability

2. **Phase B: API endpoints**
   - Add `GET /api/leader-follower/leader-debug?run_id=N`
   - Add `GET /api/leader-follower/leader-near-miss?run_id=N`
   - Extend `GET /api/leader-follower/runs` to support `since_date`/`until_date` and include `near_miss_count` when available

3. **Phase C: Bootstrap/debug mode**
   - Add `leader_follower_debug_mode: bool = False` (or `leader_follower_bootstrap_mode`) to config
   - When true, use alternate thresholds (e.g., `leader_return_threshold_pct_debug`, `leader_volume_spike_threshold_debug`) or apply a multiplier
   - Include `debug_mode: true` in run metrics when active

4. **Phase D: Multi-run inspection**
   - Extend runs endpoint with date range filters
   - Add aggregation helper or response field for per-run summaries

## Likely files/modules affected

| File | Change |
|------|--------|
| `backend/app/services/leader_follower_service.py` | Collect evaluation data; emit rejection reasons; support debug thresholds |
| `backend/app/config.py` | Add debug_mode flag and optional debug threshold overrides |
| `backend/app/api/leader_follower.py` | New routes: leader-debug, leader-near-miss; extend runs |
| `backend/app/data/repositories/` | Possibly new `leader_debug_repo` or extend `job_execution_repo` |
| `backend/app/models/` | Possibly new `LeaderDebugEvaluation` model if persisting |
| `backend/tests/` | Tests for rejection taxonomy, near-miss ranking, debug mode, new endpoints |

## Top 3 mistakes to avoid

1. **Storing excessive per-symbol data in metrics_json** — It can grow unbounded. Use a dedicated table or compute on demand.
2. **Vague rejection reasons** — Stick to the taxonomy. No free-form "other" or "unknown" without a clear fallback rule.
3. **Mixing debug thresholds with production logic** — Debug mode must be explicit and clearly signaled. Do not silently relax thresholds in production.

---

## Sequencing: Before or after evaluation/reporting work?

**Recommendation: This feature should precede or run in parallel with evaluation/reporting work.**

- **Rationale**: If evaluation/reporting builds on leader-follower outputs, those outputs are currently empty (`no_leaders`). Calibrating and debugging leader detection first will produce meaningful inputs for downstream evaluation. Building evaluation on a broken/empty pipeline is premature.
- **Parallel option**: If evaluation work is primarily schema and plumbing, it can proceed in parallel. But substantive evaluation logic that depends on leader events should wait until leader detection produces data.

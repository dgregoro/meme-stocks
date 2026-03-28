# Research: Leader Threshold Calibration and Bootstrap Debugging

**Feature**: 006-leader-threshold-calibration-and-bootstrap-debugging
**Date**: 2026-03-22

## 1. Persist vs Compute Debug Data

**Decision**: Persist evaluation data in a dedicated table `leader_debug_evaluations`.

**Rationale**:
- Compute-on-demand would require either re-running detection logic (duplicating work) or replaying from price_data (complex, error-prone). Persistence captures the run-time state at evaluation.
- Historical runs (e.g., 3 days ago) need inspection. Without persistence, we could not inspect past runs without re-triggering the job for that date.
- Table is lightweight: ~30 rows per run (grouped universe size); metrics_json per row ~200 bytes. Total ~6KB per run. Acceptable.
- Queryability: `leader-debug` and `leader-near-miss` endpoints can filter by run_id efficiently.

**Alternatives considered**:
- **metrics_json extension**: Embedding per-symbol evaluations in job_run_history.metrics_json would bloat it (30+ objects × ~200B each). Rejected: metrics_json should stay compact for status/runs; separate table is cleaner.
- **Compute on request**: Re-run detection for given run_id/event_date. Rejected: Non-idempotent; duplicates job logic; fails if price data changed.

---

## 2. Near-Miss Count and Ranking

**Decision**: Default 20 symbols for near-miss API; configurable via `limit` parameter (max 100). Rank by "proximity score": for symbols that failed on return, rank by descending `abs(return_pct)` (closest to threshold first); for volume, by descending `volume_ratio`; combined failures: use the weaker of the two constraints as tiebreaker.

**Rationale**:
- 20 is sufficient for debugging ("top 20 almost-qualified").
- Proximity score: deterministic and explainable. Primary sort: symbols that failed only one criterion rank above those that failed both. Secondary: among return-failures, higher abs(return_pct) = closer to threshold.
- Implementation: `near_miss_score = max(0, abs(return_pct) - return_threshold) + max(0, volume_ratio - vol_threshold)` inverted (smaller = closer). Or simpler: rank non-qualified symbols by `min(abs(return_pct)/threshold, 1) * min(volume_ratio/threshold, 1)` descending—highest "partial progress" first.

**Alternatives considered**:
- **Euclidean distance in normalized space**: More complex; same practical outcome for debugging.
- **Fixed 50**: Unnecessary for calibration; 20 reduces response size.

---

## 3. Debug Mode Scope

**Decision**: Global config via `leader_follower_debug_mode: bool = False` (env: `LEADER_FOLLOWER_DEBUG_MODE`). When true, use `leader_return_threshold_pct_debug` and `leader_volume_spike_threshold_debug` (or fallback to 0.5× production if not set).

**Rationale**:
- Per-run override would require passing params through job invocation (scheduler → run_detection). Adds API/CLI surface. Global config is simpler and sufficient for bootstrap phase.
- Debug mode clearly signaled in run metrics (`debug_mode: true`). Operators can see when relaxed thresholds were used.

**Alternatives considered**:
- **Per-run URL params**: e.g. `POST /jobs/leader-follower-detection?debug=true`. Rejected: job trigger API would need to accept and pass through; scheduler wouldn't use it.
- **Separate job**: `leader_follower_detection_debug`. Rejected: Duplicates job logic; two code paths.

---

## 4. Metrics JSON Size and Near-Miss Count

**Decision**: Store `near_miss_count` (int) and `debug_mode` (bool) in run metrics_json. Do not store per-symbol evaluations in metrics. Evaluations go to `leader_debug_evaluations` table.

**Rationale**:
- `near_miss_count` and `debug_mode` are scalar; negligible size impact.
- Per-symbol data stays in dedicated table. Keeps metrics_json human-readable and compact.
- Runs endpoint can include `near_miss_count` from metrics for each run without joining the evaluations table (for list view); detail endpoints hit the table.

---

## 5. Rejection Reason Taxonomy (Final)

**Decision**: Use the spec's taxonomy verbatim. Add `error` only when an exception occurs; do not add free-form sub-reasons. For `error`, optionally include sanitized context (e.g., "DataAccessError") if safe; never stack traces.

**Rationale**: Fixed set enables machine-readable filtering and aggregation. "Rejection reason distribution" (e.g., "15 below_return_threshold, 10 insufficient_volume") becomes trivial to compute.

---

## 6. Data Retention

**Decision**: No automatic retention policy in this feature. Debug evaluations persist indefinitely. Future work could add cleanup (e.g., keep last 30 days). Not in scope for 006.

**Rationale**: Bootstrap phase needs historical comparison. Retention can be added later if storage becomes a concern.

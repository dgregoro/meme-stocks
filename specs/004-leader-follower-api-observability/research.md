# Research: Leader-Follower API Observability

**Feature**: 004-leader-follower-api-observability
**Date**: 2026-03-21

## 1. Run-Before-Detection Scheduler Pattern

**Decision**: Scheduler inserts a `job_run_history` row at the start of the leader-follower detection job and passes `run_id` to `run_detection`. On success, the row is updated with metrics and summary; on failure, updated with `error_message` and `success=False`.

**Rationale**:
- `leader_events` and `leader_follower_candidates` need `job_run_id` for traceability.
- Current flow records the run only after `run_detection` returns, so `run_id` does not exist when events/candidates are created.
- Inserting at start gives a stable run_id for the entire pipeline.

**Alternatives considered**:
- **Recompute on demand**: No persistence for candidates; recompute from leader events for a given event_date. Rejected: per clarification, persist was chosen for historical debugging.
- **Record run_id after flush**: Create events, flush to get IDs, then create a run row and backfill. Rejected: complex; two-phase recording is cleaner.

**Implementation note**: Add `record_run_start(job_name, started_at) -> int` (or similar) to insert and return `id`; use existing `record_run` semantics for completion, or add `update_run(run_id, ...)` to avoid duplicating rows.

---

## 2. JobExecutionRepository Extension for Run-Start

**Decision**: Extend `JobExecutionRepository` with a method that inserts a "running" run row and returns its id. Existing `record_run` can be adapted, or a new method added (e.g., `insert_run_start` + `complete_run`).

**Rationale**: Constitution requires jobs to be observable. The current `record_run` does a full insert; we need a two-phase flow for this job only. Other jobs (Reddit, price, notification) can remain unchanged.

**Alternatives considered**:
- **Generic two-phase for all jobs**: Would require refactoring every scheduled job. Rejected: scope creep.
- **Leader-follower-specific helper**: Add logic only in `_leader_follower_detection_job`. Preferred: minimal impact.

---

## 3. Empty Reason Derivation

**Decision**: Derive `empty_reason` from run metadata and metrics:
- `no_run` — No job_run_history row for `leader_follower_detection`
- `failed` — Most recent run has `success=False`
- `no_leaders` — `leader_events_detected == 0`
- `no_candidates` — `leader_events_detected > 0` and `follower_candidates_found == 0`
- `no_confirmations` — `follower_candidates_found > 0` and `signals_emitted == 0`
- `ok` — `signals_emitted > 0`

**Rationale**: Structured, deterministic, no free-form text. Enables automated debugging and dashboards.

---

## 4. Follower Candidate Metrics (metrics_json)

**Decision**: Add `metrics_json` (TEXT, nullable) to `leader_follower_candidates`. Structure is extensible; initially may be `{}` or `null`. Future: `follower_return_pct`, `lag_days`, etc.

**Rationale**: Per clarification, store optional screening/lag metrics for evaluation. JSON allows schema evolution without migrations.

---

## 5. API Response Patterns

**Decision**: Follow existing `backend/app/api/status.py` and `leader_follower.py` patterns:
- Pydantic response models
- `Query` for params with `ge`/`le` for limits
- Datetime normalization via `ensure_utc_aware` (or equivalent) for DB values
- Structured errors per PRD Appendix C

**Rationale**: Brownfield; consistency with repo. No new middleware or response wrappers.

# Feature Specification: Leader-Follower API Observability

**Feature Name**: leader-follower-api-observability
**Feature Branch**: `004-leader-follower-api-observability`
**Created**: 2026-03-21
**Status**: Draft
**ROADMAP**: Phase 3/4 enhancement (inspectability before strategy complexity)
**Input**: Expose leader-follower pipeline internal state through read-only APIs for debugging and evaluation.

---

## Clarifications

### Session 2026-03-21

- Q: Follower candidates: persist or recompute? → A: Persist — Add `leader_follower_candidates` table; populate during `run_detection`; implement full P5 endpoint.
- Q: Access control for observability endpoints? → A: Use existing API auth — Same auth as other /api/* endpoints; no special handling.
- Q: "Relevant lag / screening metrics" for follower candidates? → A: Add metrics_json to candidates table — Store optional screening/lag metrics per candidate for future use.
- Q: Leader events filter by run_id? → A: Add run_id to leader_events — Record run row before detection, pass run_id, add FK on leader_events.
- Q: Diagnostics on empty signals when filters applied? → A: Always include when empty — Add diagnostics whenever signals=[], regardless of filters.

---

## Problem Statement

The system currently exposes final leader-follower signals via `GET /api/leader-follower/signals`, but that is insufficient for debugging and evaluation. When the endpoint returns `{"signals": []}`, users cannot determine the root cause:

- **Job never ran** — Scheduler may not have executed the leader-follower detection job, or it failed before completing
- **Upstream data missing/stale** — No price data for `event_date`, or empty tracked universe
- **No leader events detected** — Price/volume thresholds not met by any symbol
- **No follower candidates found** — Leaders detected but no group members passed the "not yet moved" filter
- **Confirmation logic filtered everything out** — Candidates found but cooldown or other rules excluded all pairs

The feature needs inspectable APIs for intermediate pipeline state so developers and researchers can debug empty results, validate detection logic, and evaluate performance without direct database access.

---

## Goals

- Make the leader-follower pipeline observable through read-only APIs
- Support debugging empty results by exposing pipeline stage counts and outcomes
- Support manual sanity-checking of recent runs
- Support future evaluation work without direct database access
- Keep the API additions minimal and aligned with current repo patterns (`backend/app/api/`, `JobExecutionRepository`, existing router structure)

---

## Non-Goals

- No trading execution changes
- No broad observability framework redesign
- No full-featured analytics dashboard
- No platform-wide API standardization effort
- No new UI work unless already trivial
- No auth redesign, scheduler refactor, client/service cleanup, retry abstraction, or sentiment integration

---

## User Stories

### User Story 1: Inspect job health

As a developer or operator, I want to retrieve recent leader-follower job run history and summary counts, so that I can determine whether the job ran successfully and what happened in each run.

**Acceptance criteria:**

- API returns recent runs for the leader-follower job
- Each run includes at minimum:
  - run timestamp (started_at, finished_at / run_at)
  - status (success / failed)
  - duration if available
  - symbols scanned / input universe size if available
  - leader events detected count
  - follower candidates detected count
  - signals emitted count
  - warning/error summary if available
- Empty state is explicit and not ambiguous (e.g., `{"runs": [], "message": "no runs found"}` or equivalent)

---

### User Story 2: Inspect recent leader events

As a developer or researcher, I want to retrieve recent detected leader events, so that I can verify whether leader detection is working and whether the events look sensible.

**Acceptance criteria:**

- API returns recent leader events
- Supports filtering by:
  - symbol (leader_symbol)
  - date/time range (event_date)
  - run id (leader_events has job_run_id FK; run recorded before detection per clarification)
- Each event includes:
  - leader symbol
  - event date
  - triggering metrics used for detection (return_pct, volume_ratio, direction)
  - grouping/relationship context if available (e.g., primary group)

---

### User Story 3: Inspect recent follower candidates

As a developer or researcher, I want to retrieve recent follower candidates, so that I can determine whether follower selection is working and whether candidates are being filtered too aggressively.

**Acceptance criteria:**

- API returns recent follower candidates
- Supports filtering by:
  - leader symbol
  - follower symbol
  - date/time range
  - run id if available
- Each candidate includes:
  - leader symbol
  - follower symbol
  - candidate timestamp / event date
  - relationship/group source (group_id)
  - optional screening/lag metrics (stored in metrics_json)
  - current status if applicable (candidate only, confirmed, rejected)

**Note:** Follower candidates will be persisted (new `leader_follower_candidates` table populated during `run_detection`) per clarification.

---

### User Story 4: Explain why no final signals were emitted

As a developer or operator, I want an API-visible explanation for why a recent run emitted zero final signals, so that I can debug the feature without reading raw logs or querying the database directly.

**Acceptance criteria:**

- When a recent run has zero signals, the API response provides enough structured information to distinguish among:
  - no run found
  - run failed (with error_message)
  - no leader events found
  - no follower candidates found
  - candidates found but no confirmations passed (e.g., all in cooldown)
- Response should prefer structured fields over free-form text

---

### User Story 5: Inspect final emitted signals with provenance

As a developer or researcher, I want emitted signals to include enough provenance to understand how they were produced, so that I can manually validate the logic and later evaluate performance.

**Acceptance criteria:**

- Final signals endpoint includes or links to:
  - source leader event (or event_date)
  - source candidate / relationship context (group_id already present)
  - confidence / score fields (strength_score, leader_return_pct, leader_volume_ratio already present)
  - timestamp (created_at, signal_date)
- Provenance should be incremental and fit existing storage/model patterns (e.g., no full schema redesign)

---

## Functional Requirements

### 1. Job Run Summary Endpoint

Define a read-only endpoint for recent leader-follower job runs that exposes:

- run status (success / failed)
- timestamps (started_at, finished_at)
- counts by pipeline stage (from existing `metrics_json`: input_universe_size, leader_events_detected, follower_candidates_found, signals_emitted)
- warnings/errors where available (error_message, summary)

### 2. Leader Events Endpoint

Define a read-only endpoint for recent leader events (from existing `leader_events` table and `LeaderEventRepository`).

### 3. Follower Candidates Endpoint

Define a read-only endpoint for recent follower candidates. Requires persisting candidates: add `leader_follower_candidates` table and populate during `run_detection` (per clarification).

### 4. Signals Endpoint Improvements

Enhance the existing `GET /api/leader-follower/signals` endpoint so empty responses are diagnostically useful. When `signals` is empty, always include a `diagnostics` block (last run summary, stage counts, empty_reason)—regardless of whether filters were applied (per clarification).

### 5. Filtering and Pagination

Support lightweight filtering and pagination appropriate for debugging/research usage (limit, since_date, leader, group—already present on signals; add analogous params for new endpoints).

### 6. Explainable Empty States

Responses must clearly distinguish between:

- no data yet (job never run)
- no matching records (filters exclude all)
- successful run with zero results (with stage counts explaining why)
- failed run (with error_message)

### 7. Consistency With Existing Repo

Use current API/router/service/repository patterns. Follow `backend/app/api/leader_follower.py`, `backend/app/api/status.py`, and `docs/ARCHITECTURE.md`. Do not invent a large new observability subsystem.

### 8. Authentication

All observability endpoints use existing API authentication (same as other `/api/*` endpoints); no special auth handling (per clarification).

---

## Data Requirements

- **Existing job run history**: `job_run_history` table and `JobExecutionRepository` already store runs for `leader_follower_detection` with `metrics_json` containing `input_universe_size`, `leader_events_detected`, `follower_candidates_found`, `signals_emitted`, `symbols_skipped`, `errors_count`. No schema change needed for job runs.
- **Leader events**: `leader_events` table will add `job_run_id` (FK to job_run_history). Scheduler records run row at start of detection, passes run_id to pipeline; events and candidates both linked to run (per clarification).
- **Existing signals**: `leader_follower_signals` table. No `leader_event_id` today; provenance is implicit via leader_symbol + signal_date.
- **Follower candidates**: Will be persisted via new `leader_follower_candidates` table (run_id, event_date, leader_symbol, follower_symbol, group_id, metrics_json). Pipeline populates during `run_detection` before `create_signals`; metrics_json stores optional screening/lag metrics per candidate.

---

## API Surface

The spec proposes concrete endpoint shapes aligned with the repo. All are under `GET /api/leader-follower/` (existing router prefix).

| Endpoint | Purpose | Query Parameters | Response Shape | Empty-State Behavior |
|----------|---------|------------------|-----------------|------------------------|
| `GET /api/leader-follower/status` | One-stop diagnostic: last run summary + quick counts | — | `last_run`, `stage_counts`, `empty_reason` | Explicit: `no_run`, `failed`, `no_leaders`, `no_candidates`, `no_confirmations`, or `ok` with counts |
| `GET /api/leader-follower/runs` | Recent job runs with full metrics | `limit` (default 20, max 100) | `runs[]`: id, run_at, started_at, duration_seconds, success, error_message, summary, metrics | `{"runs": []}` when none |
| `GET /api/leader-follower/leader-events` | Recent detected leaders | `limit`, `since_date`, `leader`, `run_id` | `events[]`: id, leader_symbol, event_date, return_pct, volume_ratio, direction, run_id, created_at | `{"events": []}` |
| `GET /api/leader-follower/follower-candidates` | Recent follower candidates | `limit`, `since_date`, `leader`, `follower` | `candidates[]`: leader_symbol, follower_symbol, event_date, group_id, run_id, metrics (from metrics_json) | `{"candidates": []}` when none |
| `GET /api/leader-follower/signals` | (Existing) Final signals | `limit`, `since_date`, `leader`, `group` | `signals[]` + `diagnostics` when empty | When empty: always add `diagnostics` (last_run_id, stage_counts, empty_reason) regardless of filters |

**Notes:**

- `status` and enhanced `signals` provide the "explain why empty" story without new data structures.
- `runs` uses existing `JobExecutionRepository.list_recent_runs(job_name="leader_follower_detection", limit=...)` and parses `metrics_json`.
- `leader-events` uses `LeaderEventRepository` with filters (including run_id once job_run_id column is added). Scheduler must record run at detection start and pass run_id into pipeline.
- `follower-candidates` uses new `leader_follower_candidates` table populated during `run_detection`.

---

## Observability Requirements

- Every leader-follower run must be externally inspectable via API at a summary level.
- The API must make it possible to answer:
  - Did the job run?
  - Did it succeed?
  - How many leaders / candidates / signals were found?
  - Where did the pipeline stop producing output?

---

## Risks / Tradeoffs

| Risk | Mitigation |
|------|------------|
| Overexposing raw internals vs useful inspectability | Limit to stage counts, dates, and IDs; avoid dumping full config or internal structures |
| Response size / pagination | Use `limit` caps (e.g., 100 for runs, 200 for events); document limits |
| Tight coupling to current internal models | Keep responses as thin projections; avoid leaking ORM details |
| Incomplete historical data for older runs | `metrics_json` exists for runs; leader_events are persisted; candidates may lack history until persisted |
| Follower candidates require new persistence | Resolved: Add `leader_follower_candidates` table; populate during `run_detection`. |

---

## Brownfield Constraints

- Prefer minimal additions; reuse existing persistence where possible.
- Avoid schema churn unless needed for stage counts or provenance.
- Keep this feature read-only.
- Do not expand scope into UI unless clearly trivial.
- Follow `backend/app/api/` router pattern and `JobExecutionRepository` / `LeaderEventRepository` / `LeaderFollowerSignalRepository` usage.

---

## Open Questions

1. **Is existing `job_run_history` sufficient?** Yes. `metrics_json` already contains the stage counts. The `status` and `runs` endpoints can be built without schema changes.

2. **Should "rejection reasons" for candidates be stored, or just stage counts?** Stage counts suffice for MVP. Storing per-candidate rejection reasons would require a new table and pipeline changes; defer unless evaluation work demands it.

3. **How much provenance should final signals expose?** Current model has leader_symbol, follower_symbol, group_id, signal_date, strength_score, leader_return_pct, leader_volume_ratio. Adding `leader_event_id` (FK to leader_events) would enable traceability; optional for MVP. The `diagnostics` block on empty responses can provide run-level context without schema change.

4. **Follower candidates: persist or recompute?** **Resolved: Persist.** Add `leader_follower_candidates` table (run_id, event_date, leader_symbol, follower_symbol, group_id) populated during `run_detection`.

---

## Recommended MVP API Set

| Priority | Endpoint | Rationale |
|----------|----------|-----------|
| P1 | `GET /api/leader-follower/status` | Single call answers "why empty?" with last run and stage counts |
| P2 | `GET /api/leader-follower/runs` | Full run history for debugging; uses existing data |
| P3 | `GET /api/leader-follower/leader-events` | Inspect leader detection output; uses existing table |
| P4 | Enhance `GET /api/leader-follower/signals` | Add `diagnostics` when empty; no new endpoints |
| P5 | `GET /api/leader-follower/follower-candidates` | Uses persisted candidates; implement after leader_follower_candidates table is added |

---

## Recommended Endpoint Order of Implementation

1. **`GET /api/leader-follower/status`** — New endpoint; reads last run from `JobExecutionRepository`, parses metrics, returns structured `empty_reason`.
2. **`GET /api/leader-follower/runs`** — New endpoint; wraps `list_recent_runs("leader_follower_detection")` with metrics parsing.
3. **`GET /api/leader-follower/leader-events`** — New endpoint; add `job_run_id` to leader_events, update scheduler to record run at start and pass run_id to pipeline; then wrap `LeaderEventRepository.list_recent` with filters (including run_id).
4. **Enhance `GET /api/leader-follower/signals`** — Add `diagnostics` when `signals` is empty (last run summary, stage counts, empty_reason).
5. **`GET /api/leader-follower/follower-candidates`** — New endpoint; add `leader_follower_candidates` table and populate in `run_detection` first, then implement endpoint.

---

## Minimal Persistence Additions

| Addition | When Required | Description |
|----------|---------------|-------------|
| None for status, runs | P1–P2 | Uses existing job_run_history; no schema change |
| `job_run_id` on `leader_events` | **Required for P3** | Add FK to job_run_history. Scheduler records run row at detection start, passes run_id to `run_detection`; events linked to run. |
| `leader_follower_candidates` table | **Required for P5** | Columns: id, job_run_id (FK), event_date, leader_symbol, follower_symbol, group_id, metrics_json, created_at. Populate in `run_detection` before `create_signals`. |
| `leader_event_id` on `leader_follower_signals` | Optional provenance | FK to leader_events; set when creating signal. Enables traceability from signal back to leader event. |

For P1–P2, no persistence additions. For P3, add `job_run_id` to `leader_events` and update scheduler flow. For P5, `leader_follower_candidates` table is required. All per clarifications.

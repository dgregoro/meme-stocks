# Tasks: Leader-Follower API Observability

**Input**: Design documents from `specs/004-leader-follower-api-observability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Project requires tests for new backend logic (.cursorrules). Each endpoint gets at least one test.

**Organization**: Tasks grouped by user story and implementation order (P1→P5).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verify Environment)

**Purpose**: Confirm brownfield project ready; no new structure needed

- [x] T001 Verify backend runs and existing leader-follower job via `pytest backend/tests/test_leader_follower_api.py -v -k list_signals` (run from repo root)

---

## Phase 2: User Story 1 / P1 - GET /api/leader-follower/status

**Goal**: One-stop diagnostic endpoint answering "why are there no signals?"

**Independent Test**: `GET /api/leader-follower/status` returns 200 with `last_run`, `stage_counts`, `empty_reason`; when no run exists returns `empty_reason: "no_run"`

### Implementation

- [x] T002 [P] [US1] Add `_derive_empty_reason` helper in `backend/app/api/leader_follower.py` (metrics → no_run, failed, no_leaders, no_candidates, no_confirmations, ok)
- [x] T003 [US1] Add `GET /api/leader-follower/status` endpoint in `backend/app/api/leader_follower.py`; response model: last_run, stage_counts, empty_reason per contracts/observability-api.md
- [x] T004 [US1] Add integration test for status endpoint in `backend/tests/test_leader_follower_api.py`: no_run, failed run, successful run with zero signals, successful run with signals

**Checkpoint**: Status endpoint works; answers "why empty?"

---

## Phase 3: User Story 1 / P2 - GET /api/leader-follower/runs

**Goal**: Recent job runs with full metrics for debugging

**Independent Test**: `GET /api/leader-follower/runs?limit=10` returns 200 with `runs[]`; each run has id, run_at, started_at, duration_seconds, success, error_message, summary, metrics

### Implementation

- [x] T005 [P] [US1] Add `GET /api/leader-follower/runs` endpoint in `backend/app/api/leader_follower.py`; query param limit (default 20, max 100); wraps JobExecutionRepository.list_recent_runs("leader_follower_detection"); parse metrics_json
- [x] T006 [US1] Add integration test for runs endpoint in `backend/tests/test_leader_follower_api.py`: empty, with runs, metrics parsed

**Checkpoint**: Status + runs both work; US1 complete

---

## Phase 4: User Story 2 / P3 - GET /api/leader-follower/leader-events

**Goal**: Recent leader events with run_id linkage and filters

**Independent Test**: `GET /api/leader-follower/leader-events` returns 200 with `events[]`; supports filters leader, since_date, run_id

### Schema & Pipeline

- [x] T007 Add migration for `job_run_id` on leader_events in `backend/app/data/database.py` (add_column_if_missing pattern; FK job_run_history.id)
- [x] T008 [P] Add `job_run_id` column to LeaderEvent model in `backend/app/models/leader_event.py`
- [x] T009 Add `insert_run_start` and `complete_run` methods to JobExecutionRepository in `backend/app/data/repositories/job_execution_repo.py` (insert run at start, return id; update on completion)
- [x] T010 Update `_leader_follower_detection_job` in `backend/app/services/scheduler_service.py`: call insert_run_start at start, pass run_id to run_detection; on success call complete_run with metrics; on failure call complete_run with error_message
- [x] T011 Update `run_detection` in `backend/app/services/leader_follower_service.py` to accept optional `run_id`; pass to `detect_leaders`
- [x] T012 Update `detect_leaders` in `backend/app/services/leader_follower_service.py` to accept `run_id`; pass to LeaderEventRepository.add when creating events
- [x] T013 Update LeaderEventRepository.add in `backend/app/data/repositories/leader_event_repo.py` to accept job_run_id; add `list_recent` filter by run_id, since_date, leader
- [x] T014 [US2] Add `GET /api/leader-follower/leader-events` endpoint in `backend/app/api/leader_follower.py`; query params limit, since_date, leader, run_id
- [x] T015 [US2] Add integration test for leader-events endpoint in `backend/tests/test_leader_follower_api.py`

**Checkpoint**: Leader events endpoint works; events linked to runs

---

## Phase 5: User Story 4 / P4 - Enhance signals with diagnostics

**Goal**: When signals=[] always include diagnostics (empty_reason, stage_counts)

**Independent Test**: `GET /api/leader-follower/signals` with no signals returns 200 with `signals: []` and `diagnostics` block

### Implementation

- [x] T016 [US4] Add diagnostics logic to `list_signals` in `backend/app/api/leader_follower.py`: when signals empty, fetch last run, derive empty_reason, include diagnostics (last_run_id, last_run_at, stage_counts, empty_reason) per contracts
- [x] T017 [US4] Add response model or union for SignalsResponse with optional diagnostics; ensure diagnostics always present when signals empty
- [x] T018 [US4] Add integration test: signals empty returns diagnostics in `backend/tests/test_leader_follower_api.py`

**Checkpoint**: Signals endpoint diagnostically useful when empty

---

## Phase 6: User Story 3 / P5 - GET /api/leader-follower/follower-candidates

**Goal**: Recent follower candidates from persisted table

**Independent Test**: `GET /api/leader-follower/follower-candidates` returns 200 with `candidates[]`; supports filters leader, follower, since_date, run_id

### Schema & Pipeline

- [x] T019 Add migration for `leader_follower_candidates` table in `backend/app/data/database.py` (CREATE TABLE if not exists; columns per data-model.md)
- [x] T020 [P] Create LeaderFollowerCandidate model in `backend/app/models/leader_follower_candidate.py`
- [x] T021 [P] Create LeaderFollowerCandidateRepository in `backend/app/data/repositories/leader_follower_candidate_repo.py` with list_recent and add methods
- [x] T022 Update `run_detection` in `backend/app/services/leader_follower_service.py` to persist candidates: after select_follower_candidates loop, insert each (leader_symbol, follower_symbol, group_id) into LeaderFollowerCandidateRepository with job_run_id, event_date, metrics_json (initially null)
- [x] T023 [US3] Add `GET /api/leader-follower/follower-candidates` endpoint in `backend/app/api/leader_follower.py`; query params limit, since_date, leader, follower, run_id (per spec)
- [x] T024 [US3] Add integration test for follower-candidates endpoint in `backend/tests/test_leader_follower_api.py`

**Checkpoint**: All five endpoints implemented; pipeline persists candidates

---

## Phase 7: Polish & Cross-Cutting

- [x] T025 [P] Run `./scripts/verify.sh`; fix any failures
- [x] T026 Update quickstart.md if any endpoint shape changed from contracts
- [x] T027 [P] Verify contracts/observability-api.md matches implemented API shapes
- [x] T028 Register models in `backend/app/models/__init__.py` if LeaderFollowerCandidate needs export

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2–3 (US1)**: Depends on Phase 1; no schema change
- **Phase 4 (US2)**: Depends on Phase 1; requires schema (job_run_id) and scheduler change
- **Phase 5 (US4)**: Depends on Phase 1; enhances existing signals endpoint
- **Phase 6 (US3)**: Depends on Phase 4 (run_id flow); requires new table and pipeline change
- **Phase 7**: Depends on Phases 2–6

### User Story Dependencies

- **US1 (status, runs)**: Independent; no dependencies on other stories
- **US2 (leader-events)**: Independent; requires run_id flow
- **US4 (signals diagnostics)**: Independent; reads job_run_history
- **US3 (follower-candidates)**: Depends on run_id flow (Phase 4) and new table

### Parallel Opportunities

- T002 and T005 can be done in parallel (different logic blocks)
- T008, T020, T021 are model/repo tasks that can parallelize within their phases
- T025, T026, T027, T028 in Polish can run in parallel

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: Verify
2. Phase 2: status endpoint
3. Phase 3: runs endpoint
4. **STOP**: Validate status + runs; deploy/demo

### Incremental Delivery

1. Phases 1–3 → US1 complete (status + runs)
2. Phase 4 → US2 (leader-events) + run_id flow
3. Phase 5 → US4 (signals diagnostics)
4. Phase 6 → US3 (follower-candidates)
5. Phase 7 → Polish

### Suggested MVP Scope

**Phases 1–3 only** — status and runs deliver the primary "why empty?" value with zero schema change.

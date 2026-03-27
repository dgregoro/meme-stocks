# Tasks: Leader Threshold Calibration and Bootstrap Debugging

**Input**: Design documents from `specs/006-leader-threshold-calibration-and-bootstrap-debugging/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution (backend logic changes require tests).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verification)

**Purpose**: Verify brownfield environment before making changes

- [X] T001 Run `pytest backend/tests/ -v` from project root and confirm tests pass
- [X] T002 [P] Confirm `backend/app/services/leader_follower_service.py`, `backend/app/api/leader_follower.py`, and `backend/app/config.py` exist and match plan

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Model, migration, repository, and config required before service/API changes

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [US1] Create `LeaderDebugEvaluation` model in `backend/app/models/leader_debug_evaluation.py` with job_run_id, stock_symbol, return_pct, volume_ratio, qualified_as_leader, rejection_reasons (JSON text), metrics_json, created_at
- [X] T004 [US1] Add migration in `backend/app/data/database.py` to create `leader_debug_evaluations` table (follow `_migrate_create_leader_follower_candidates` pattern); register model in `main.py` imports
- [X] T005 [US1] Create `LeaderDebugRepository` in `backend/app/data/repositories/leader_debug_repo.py` with `add(eval)`, `list_by_run_id(run_id, limit)`, `list_near_misses_by_run_id(run_id, limit)`
- [X] T006 [US3] Add to `backend/app/config.py`: `leader_follower_debug_mode: bool = False`, `leader_return_threshold_pct_debug: float = 3.0`, `leader_volume_spike_threshold_debug: float = 1.2` (env: LEADER_FOLLOWER_DEBUG_MODE, etc.)
- [X] T007 [P] [US1] Add unit tests for `LeaderDebugRepository` in `backend/tests/test_leader_debug_repo.py` (add, list_by_run_id, list_near_misses filters and ordering)

**Checkpoint**: Model, repo, config exist; service can persist evaluations

---

## Phase 3: User Story 1 — Symbol-Level Evaluation and Rejection Reasons (Priority: P1) 🎯 MVP

**Goal**: For each run, capture evaluated symbols with return_pct, volume_ratio, qualified_as_leader, rejection_reasons. Persist and expose via API.

**Independent Test**: Trigger job; GET leader-debug?run_id=N returns evaluations with rejection_reasons from taxonomy.

### Implementation for User Story 1

- [X] T008 [US1] In `backend/app/services/leader_follower_service.py`, modify `detect_leaders` to collect evaluation records (symbol, return_pct, volume_ratio, qualified, rejection_reasons) for each symbol; use rejection taxonomy: insufficient_bars, no_data_on_event_date, zero_avg_volume, below_return_threshold, insufficient_volume, error
- [X] T009 [US1] In `run_detection` in `backend/app/services/leader_follower_service.py`, persist evaluations to LeaderDebugRepository after detect_leaders; compute and add near_miss_count to metrics (count of non-qualified with return_pct and volume_ratio present)
- [X] T010 [P] [US1] Add service tests in `backend/tests/test_leader_follower_service.py` for rejection taxonomy (each reason path) and evaluation collection

**Checkpoint**: User Story 1 — evaluations persisted; near_miss_count in metrics

---

## Phase 4: User Story 2 — Near-Miss API (Priority: P2)

**Goal**: Expose top near-miss symbols via GET leader-near-miss.

**Independent Test**: GET /api/leader-follower/leader-near-miss?run_id=N returns near-misses ranked by proximity.

### Implementation for User Story 2

- [X] T011 [US2] Add `GET /api/leader-follower/leader-debug` in `backend/app/api/leader_follower.py`: run_id (required), limit (default 50); return run_id, event_date, evaluated_count, leaders_count, evaluations list; 404 if run missing
- [X] T012 [US2] Add `GET /api/leader-follower/leader-near-miss` in `backend/app/api/leader_follower.py`: run_id (required), limit (default 20); return near_misses from repo; 404 if run missing
- [X] T013 [P] [US2] Add API tests in `backend/tests/test_leader_follower_api.py` for leader-debug and leader-near-miss (happy path, 404, empty)

**Checkpoint**: User Stories 1 and 2 — leader-debug and leader-near-miss endpoints work

---

## Phase 5: User Story 4 — Multi-Run Inspection (Priority: P3)

**Goal**: Query runs over date range; include near_miss_count in response.

**Independent Test**: GET /api/leader-follower/runs?since_date=X&until_date=Y returns filtered runs with near_miss_count in metrics.

### Implementation for User Story 4

- [X] T014 [US4] Extend `GET /api/leader-follower/runs` in `backend/app/api/leader_follower.py` with query params since_date, until_date; filter by run_at
- [X] T015 [US4] Ensure JobExecutionRepository (or equivalent) supports date filtering; pass through to list_recent_runs or extend repo
- [X] T016 [P] [US4] Add API test for runs with since_date, until_date and near_miss_count in response

**Checkpoint**: User Story 4 — multi-run inspection with date filters

---

## Phase 6: User Story 3 — Bootstrap/Debug Mode (Priority: P4)

**Goal**: Configurable debug mode with relaxed thresholds; debug_mode visible in metrics.

**Independent Test**: Set LEADER_FOLLOWER_DEBUG_MODE=true; trigger job; metrics include debug_mode: true; relaxed thresholds used.

### Implementation for User Story 3

- [X] T017 [US3] In `detect_leaders` in `backend/app/services/leader_follower_service.py`, when `leader_follower_debug_mode` is true, use `leader_return_threshold_pct_debug` and `leader_volume_spike_threshold_debug` instead of production thresholds
- [X] T018 [US3] In `run_detection`, add `debug_mode: true` to metrics when `leader_follower_debug_mode` is true
- [X] T019 [P] [US3] Add service test that detect_leaders uses debug thresholds when debug_mode enabled; add test that metrics include debug_mode

**Checkpoint**: User Story 3 — debug mode functional; User Story 5 preserved (no empty_reason changes)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup

- [X] T020 Run `./scripts/verify.sh` from project root and fix any failures
- [X] T021 [P] Verify quickstart.md steps: trigger job, GET leader-debug, leader-near-miss, runs with date filter; confirm debug mode when enabled

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS user stories
- **Phase 3 (US1)**: Depends on Phase 2 (model, repo, config)
- **Phase 4 (US2)**: Depends on Phase 3 (evaluations persisted)
- **Phase 5 (US4)**: Depends on Phase 2; can run in parallel with Phase 4 after Phase 3
- **Phase 6 (US3)**: Depends on Phase 2 (config); can run in parallel with Phase 4/5
- **Phase 7 (Polish)**: Depends on Phases 3–6

### User Story Dependencies

- **US1**: Requires T003–T007 (model, migration, repo)
- **US2**: Requires US1 (evaluations must be persisted)
- **US3**: Requires T006 (config); independent of US1/US2
- **US4**: Requires Phase 2; extends existing runs endpoint
- **US5**: No new tasks; preserved by not changing empty_reason logic

### Parallel Opportunities

- T002, T007 can run in parallel
- T011, T012 can run in parallel
- T014–T016 (US4) can run after Phase 2; T017–T019 (US3) can run in parallel with Phase 4

---

## Implementation Strategy

### MVP First (User Story 1 + US2 APIs)

1. Phase 1: Setup
2. Phase 2: Foundational (model, repo, config)
3. Phase 3: US1 — Rejection taxonomy + evaluation collection + persistence
4. Phase 4: US2 — leader-debug, leader-near-miss endpoints
5. **STOP and VALIDATE**: Trigger job, GET leader-debug, leader-near-miss
6. Then Phase 5 (US4), Phase 6 (US3), Phase 7

### Incremental Delivery

1. Phase 1–2 → Foundation
2. Phase 3–4 → MVP (understand why no leaders, inspect near-misses)
3. Phase 5 → Multi-run inspection
4. Phase 6 → Debug mode
5. Phase 7 → Polish

---

## Notes

- Rejection taxonomy: insufficient_bars, no_data_on_event_date, zero_avg_volume, below_return_threshold, insufficient_volume, error
- Near-miss: symbols with return_pct and volume_ratio (failed on thresholds only); rank by proximity
- Do not change follower logic; do not store per-symbol data in metrics_json
- Use `datetime.now(timezone.utc)` for created_at (not utcnow)

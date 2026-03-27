# Tasks: Leader-Follower Signal Evaluation and Review

**Input**: Design documents from `/specs/007-leader-follower-signal-evaluation-and-review/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add follower/until_date filters to signal repository; no new project structure.

- [x] T001 Add `follower` and `until_date` filters to `list_signals` in `backend/app/data/repositories/leader_follower_signal_repo.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Evaluation service with forward-return and aggregation logic.

- [x] T002 Implement `LeaderFollowerEvaluationService` in `backend/app/services/leader_follower_evaluation_service.py` with: `compute_forward_return`, `evaluate_signal`, `aggregate_summary`, `aggregate_by_pair`, `compute_duplicate_overlap`
- [x] T003 Add config constants for evaluation horizons (1,3,5) and overlap window (5) in `backend/app/config.py`

---

## Phase 3: User Story 1 — View Summary Performance (P1) MVP

**Goal**: API returns summary metrics for leader-follower signals.

**Independent Test**: `GET /api/leader-follower/evaluation/summary` returns total_signals, by_horizon with win_rate, avg_return_pct, evaluable_count.

- [x] T004 [US1] Add evaluation summary route `GET /api/leader-follower/evaluation/summary` in `backend/app/api/leader_follower.py` with query params since_date, until_date, leader, follower
- [x] T005 [US1] Implement summary handler calling evaluation service; return Pydantic response per contracts/evaluation-api.md

---

## Phase 4: User Story 2 — Evaluate by Leader/Follower Pair (P2)

**Goal**: Results grouped by leader/follower pair with signal count, win rate, avg return.

**Independent Test**: `GET /api/leader-follower/evaluation/pairs` returns pairs array with per-horizon metrics.

- [x] T006 [US2] Add evaluation pairs route `GET /api/leader-follower/evaluation/pairs` in `backend/app/api/leader_follower.py`
- [x] T007 [US2] Implement pairs handler with filters (since_date, until_date, leader, follower, limit)

---

## Phase 5: User Story 3 — Review Best and Worst Pairs (P3)

**Goal**: Top/bottom pairs by chosen metric with min_sample protection.

**Independent Test**: `GET /api/leader-follower/evaluation/top-pairs` and `bottom-pairs` return ranked pairs.

- [x] T008 [US3] Add `GET /api/leader-follower/evaluation/top-pairs` and `GET /api/leader-follower/evaluation/bottom-pairs` in `backend/app/api/leader_follower.py`
- [x] T009 [US3] Implement handlers with query params n, metric, horizon, min_sample

---

## Phase 6: User Story 4 — Understand Duplicate and Overlap Behavior (P4)

**Goal**: Duplicate/overlap count in summary; repeat signals within window.

**Independent Test**: Summary response includes duplicate_overlap with repeat_pair_in_window, window_days.

- [x] T010 [US4] Ensure `compute_duplicate_overlap` is called in aggregate_summary and included in summary response (already in T002)

---

## Phase 7: User Story 5 — Review Individual Signal Outcomes (P5)

**Goal**: Signal-level rows with entry price, forward returns, win/loss by horizon.

**Independent Test**: `GET /api/leader-follower/evaluation/signals` returns signals with entry_price and horizon outcomes.

- [x] T011 [US5] Add `GET /api/leader-follower/evaluation/signals` in `backend/app/api/leader_follower.py`
- [x] T012 [US5] Implement signals handler with filters and pagination via limit

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T013 Add unit tests for `leader_follower_evaluation_service` in `backend/tests/test_leader_follower_evaluation_service.py`
- [x] T014 Add API tests for evaluation endpoints in `backend/tests/test_leader_follower_api.py`
- [x] T015 Run `./scripts/verify.sh` and fix any failures
- [ ] T016 Run quickstart verification steps from `specs/007-leader-follower-signal-evaluation-and-review/quickstart.md`

---

## Dependencies & Execution Order

| Phase | Depends on | Blocks |
|-------|------------|--------|
| 1 Setup | — | 2 |
| 2 Foundational | 1 | 3–7 |
| 3 US1 | 2 | — |
| 4 US2 | 2 | — |
| 5 US3 | 2, 4 | — |
| 6 US4 | 2, 3 | — |
| 7 US5 | 2 | — |
| 8 Polish | 3–7 | — |

**Parallel**: US2, US3, US4, US5 can proceed in parallel after Phase 2.

## Implementation Strategy

**MVP First**: Phases 1–3 (Setup → Foundational → US1 Summary). Validate summary endpoint.

**Incremental**: Add pairs (US2) → top/bottom (US3) → overlap in summary (US4) → signals (US5) → tests (Polish).

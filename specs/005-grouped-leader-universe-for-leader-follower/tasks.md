# Tasks: Grouped Leader Universe for Leader-Follower

**Input**: Design documents from `specs/005-grouped-leader-universe-for-leader-follower/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution (backend logic changes require tests).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verification)

**Purpose**: Verify brownfield environment before making changes

- [X] T001 Run `pytest backend/tests/ -v` and confirm all tests pass from project root
- [X] T002 [P] Confirm `backend/app/data/repositories/stock_group_repo.py` and `backend/app/services/leader_follower_service.py` exist and match plan

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository method required before leader detection changes

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add `get_all_symbols() -> list[str]` to StockGroupRepository in `backend/app/data/repositories/stock_group_repo.py` returning distinct stock_symbols from stock_groups ordered lexicographically
- [X] T004 [P] Add unit test for `get_all_symbols()` in `backend/tests/test_stock_group_repo.py` (empty, single group, multiple groups with overlapping symbols)

**Checkpoint**: Grouped symbol set is obtainable; service can call `stock_group_repo.get_all_symbols()`

---

## Phase 3: User Story 1 — Coherent Bootstrap Leader Detection (Priority: P1) — MVP

**Goal**: Leader detection uses only symbols present in stock_groups; any detected leader has a plausible path to follower candidates.

**Independent Test**: Run leader-follower job with stock_groups seeded; `leader_events_detected` counts only leaders from grouped symbols; ungrouped symbols (e.g. UMAC) no longer appear as leaders.

### Implementation for User Story 1

- [X] T005 [US1] In `backend/app/services/leader_follower_service.py`, change `detect_leaders()` to iterate over `stock_group_repo.get_all_symbols()` instead of `stock_repo.list()`; pass stock_group_repo into detect_leaders (or obtain from db inside)
- [X] T006 [US1] In `run_detection()` in `backend/app/services/leader_follower_service.py`, short-circuit when `get_all_symbols()` is empty: skip leader detection, return metrics with `grouped_leader_universe_size: 0`, `leader_events_detected: 0`, `follower_candidates_found: 0`, `signals_emitted: 0`
- [X] T007 [US1] In `run_detection()`, add `grouped_leader_universe_size` to the returned metrics dict (compute before detect_leaders; use len(get_all_symbols()))
- [X] T008 [US1] Add service test in `backend/tests/test_leader_follower_service.py` that when stock_groups is empty, run_detection returns 0 leaders and grouped_leader_universe_size 0
- [X] T009 [US1] Add service test in `backend/tests/test_leader_follower_service.py` that when stock_groups has symbols, detect_leaders only considers those symbols (e.g. leader from grouped symbol appears; ungrouped symbol with big move does not)

**Checkpoint**: User Story 1 complete — leader detection restricted to grouped universe; run and verify manually

---

## Phase 4: User Story 2 & 3 — Observability (Priorities: P2, P3)

**Goal**: Diagnostics show grouped_leader_universe_size; empty_reason distinguishes stock_groups_empty.

**Independent Test**: GET /api/leader-follower/status returns `stage_counts.grouped_leader_universe_size`; when stock_groups empty, `empty_reason` is `stock_groups_empty`.

### Implementation for User Story 2 & 3

- [X] T010 [US2] Extend `StageCounts` in `backend/app/api/leader_follower.py` with `grouped_leader_universe_size: int = 0`
- [X] T011 [US2] In `get_status()`, populate `stage_counts.grouped_leader_universe_size` from metrics (default 0 when absent for older runs)
- [X] T012 [US3] In `_derive_empty_reason()` in `backend/app/api/leader_follower.py`, add check for `grouped_leader_universe_size == 0` before `no_leaders`; return `stock_groups_empty` when grouped universe is 0
- [X] T013 [US3] Update `EmptyReason` type to include `"stock_groups_empty"`
- [X] T014 [P] [US2] Add API test in `backend/tests/test_leader_follower_api.py` that status response includes `grouped_leader_universe_size` when run has metrics
- [X] T015 [P] [US3] Add API test in `backend/tests/test_leader_follower_api.py` that when last run has `grouped_leader_universe_size: 0`, `empty_reason` is `stock_groups_empty`

**Checkpoint**: User Stories 2 and 3 complete — diagnostics show grouped universe and explain empty stock_groups

---

## Phase 5: User Story 4 — Documentation (Priority: P4)

**Goal**: Docs explain bootstrap-phase leader scoping and limitations.

**Independent Test**: Read `docs/STOCK_GROUPS_BOOTSTRAP.md`; it states that leader detection is scoped to grouped symbols during bootstrap.

### Implementation for User Story 4

- [X] T016 [US4] Update `docs/STOCK_GROUPS_BOOTSTRAP.md` to document that leader detection is restricted to symbols in stock_groups during the bootstrap phase
- [X] T017 [US4] Add subsection explaining why this is intentional (coherent pipeline, debuggability) and future direction (learned relationships)
- [X] T018 [US4] Ensure docs do not overclaim this as true follower discovery

**Checkpoint**: User Story 4 complete — docs aligned with behavior

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup

- [X] T019 Run `./scripts/verify.sh` from project root and fix any failures
- [ ] T020 [P] Verify quickstart.md steps: seed stock-groups, trigger job, inspect status with `grouped_leader_universe_size` and `empty_reason`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS user stories
- **Phase 3 (US1)**: Depends on Phase 2 (get_all_symbols exists)
- **Phase 4 (US2+US3)**: Depends on Phase 3 (run_detection returns grouped_leader_universe_size)
- **Phase 5 (US4)**: Can run in parallel with Phase 4 or after
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5

### User Story Dependencies

- **US1**: Requires T003 (get_all_symbols)
- **US2**: Requires US1 (metrics from run_detection)
- **US3**: Requires US2 (stage_counts has grouped_leader_universe_size for empty_reason logic)
- **US4**: Independent; can run after US1

### Parallel Opportunities

- T002, T004 can run in parallel within their phases
- T014, T015 can run in parallel
- T016–T018 can run in parallel
- T020 can run in parallel with T019 (different validation focus)

---

## Parallel Example: Phase 4

```bash
# API tests in parallel:
Task T014: "Add API test for grouped_leader_universe_size in stage_counts"
Task T015: "Add API test for empty_reason stock_groups_empty"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (get_all_symbols + test)
3. Phase 3: User Story 1 (restrict detect_leaders, metrics, short-circuit, tests)
4. **STOP and VALIDATE**: Trigger job, verify only grouped symbols become leaders
5. Deploy/demo if ready

### Incremental Delivery

1. Phase 1–2 → Foundation
2. Phase 3 (US1) → Coherent leader detection (MVP!)
3. Phase 4 (US2+US3) → Observable diagnostics
4. Phase 5 (US4) → Docs
5. Phase 6 → Polish

---

## Notes

- [P] tasks = different files or no ordering constraint
- [Story] label maps task to user story for traceability
- Constitution requires tests for service/repository/API changes
- Run `./scripts/verify.sh` before considering done

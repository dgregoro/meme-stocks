# Tasks: Mean reversion after extreme moves (016)

**Input**: Design documents from `/specs/016-mean-reversion-after-extreme-moves/`

## Dependencies (user stories)

```text
US1 (detect) + US2 (classify) → US3 (persist) → US4 (evaluate) → US5 (API/CLI)
```

## Phase 1: Setup

- [x] T001 Add config keys in `backend/app/config.py` (`extreme_move_up_threshold_pct`, `extreme_move_down_threshold_pct`, `extreme_move_research_horizons`, `extreme_move_research_min_close`)

## Phase 2: Foundational

- [x] T002 Add SQLAlchemy model `ExtremeMoveEvent` in `backend/app/models/extreme_move_event.py`
- [x] T003 Register model in `backend/app/main.py` imports for `create_all`
- [x] T004 Register model in `backend/app/cli.py` imports for `init_db`
- [x] T005 Implement `ExtremeMoveEventRepository` in `backend/app/data/repositories/extreme_move_event_repo.py`

## Phase 3: User Story 1 — Detect extreme moves (P1)

**Independent test**: Controlled price series crosses ±threshold predictably.

- [x] T006 [US1] Implement `compute_daily_return_pct` and helpers in `backend/app/services/extreme_move_detection.py`
- [x] T007 [P] [US1] Add unit tests in `backend/tests/test_extreme_move_detection.py`
- [x] T008 [US1] Implement `backfill_extreme_moves` in `backend/app/services/extreme_move_service.py`
- [x] T009 [US1] Add integration tests in `backend/tests/test_extreme_move_service.py`

## Phase 4: User Story 2 — Classify (P1)

**Independent test**: Tie-break and threshold edge cases covered in unit tests.

- [x] T010 [US2] Implement `classify_extreme_move` in `backend/app/services/extreme_move_detection.py` (same file as T006)
- [x] T011 [P] [US2] Extend `backend/tests/test_extreme_move_detection.py` for classification and tie-break

## Phase 5: User Story 3 — Persist (P1)

**Independent test**: Upsert idempotent; `replace_range` deletes then refills.

- [x] T012 [US3] Use repository upsert/delete from `extreme_move_event_repo.py` in backfill service (T008)
- [x] T013 [P] [US3] Service tests for upsert and replace_range in `backend/tests/test_extreme_move_service.py`

## Phase 6: User Story 4 — Evaluate forward returns (P1)

**Independent test**: Aggregates match known price paths.

- [x] T014 [US4] Implement evaluation in `backend/app/services/extreme_move_evaluation_service.py` (reuse `compute_forward_return`)
- [x] T015 [P] [US4] Add unit tests in `backend/tests/test_extreme_move_evaluation_service.py`

## Phase 7: User Story 5 — Read-only API and CLI (P1)

**Independent test**: HTTP list/filter/summary; CLI echoes JSON.

- [x] T016 [US5] Add router `backend/app/api/extreme_move.py` and `include_router` in `backend/app/main.py`
- [x] T017 [US5] Add Typer commands `backfill extreme-move` and `evaluate extreme-move` in `backend/app/cli.py`
- [x] T018 [P] [US5] Add API integration tests in `backend/tests/test_extreme_move_api.py`
- [x] T019 [P] [US5] Extend `backend/tests/test_config.py` for new settings defaults

## Phase 8: Polish

- [x] T020 Document Phase 3.14 in `docs/ROADMAP.md`
- [x] T021 Run `./scripts/verify.sh` (pre-commit + full `pytest backend/tests/`)

## Parallel examples

- T007, T011 after T006
- T009, T013 after T008
- T015 after T014
- T018, T019 after T016–T017

## Implementation strategy

MVP: config + model + repo + detection + backfill + evaluation + `/api/extreme-move/*` + CLI; mirror `015` volume-spike patterns.

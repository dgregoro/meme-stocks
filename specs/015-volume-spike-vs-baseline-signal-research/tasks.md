# Tasks: Volume spike vs baseline signal research (015)

**Input**: `/specs/015-volume-spike-vs-baseline-signal-research/` (plan.md, spec.md, data-model.md, contracts/)

## Phase 1: Setup

- [X] T001 Add `volume_spike_research_*` settings in `backend/app/config.py`

## Phase 2: Foundational

- [X] T002 Add SQLAlchemy model `VolumeSpikeEvent` in `backend/app/models/volume_spike_event.py`
- [X] T003 Register model in `backend/app/main.py` and `backend/app/cli.py` imports for metadata
- [X] T004 Add `VolumeSpikeEventRepository` in `backend/app/data/repositories/volume_spike_event_repo.py`

## Phase 3: User Story 1–3 (P1) — Detect, classify, evaluate

**Goal**: Pure detection math, persistence, forward-return aggregates.

**Independent test**: Unit tests on detection; evaluation with known price path.

- [X] T005 [US1] Add pure functions in `backend/app/services/volume_spike_detection.py` (baseline, ratio, classification)
- [X] T006 [US1] [US2] [US3] Add `volume_spike_evaluation_service.py` in `backend/app/services/volume_spike_evaluation_service.py` (reuse `compute_forward_return`)
- [X] T007 [US1] [US2] Implement `volume_spike_service.py` in `backend/app/services/volume_spike_service.py` (`backfill_range`, config wiring)
- [X] T008 [P] [US1] [US2] [US3] Unit tests in `backend/tests/test_volume_spike_detection.py`
- [X] T009 [US3] Unit tests in `backend/tests/test_volume_spike_evaluation_service.py`

## Phase 4: User Story 4 (P2) — CLI backfill

- [X] T010 [US4] Add `backfill volume-spike` command in `backend/app/cli.py`

## Phase 5: User Story 5 (P2) — API + CLI evaluate

- [X] T011 [US5] Add read-only router `backend/app/api/volume_spike.py` and register in `backend/app/main.py`
- [X] T012 [US5] Add `evaluate volume-spike` command in `backend/app/cli.py`
- [X] T013 [P] [US5] Integration tests in `backend/tests/test_volume_spike_api.py`

## Phase 6: Polish

- [X] T014 Update `docs/ROADMAP.md` with 015 research item (if required by project rules)
- [X] T015 Run `./scripts/verify.sh` and mark tasks complete

## Dependencies

- T001 → T002–T007
- T002 → T003, T004, T007, T011
- T004 → T007, T011
- T005 → T007, T008
- T006 → T009, T011
- T007 → T010, T012
- T011 → T013

## Parallel (after Phase 2)

- T005 and T006 can proceed in parallel after T001
- T008 parallel to T009 after T005/T006

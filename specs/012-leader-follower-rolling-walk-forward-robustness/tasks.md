# Tasks: Leader-follower rolling walk-forward robustness (012)

**Input**: Design documents from `/specs/012-leader-follower-rolling-walk-forward-robustness/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Dependencies (user story order)

```text
Phase 1 Setup → Phase 2 Foundational → US1 splits → US2 candidates → US3 persistence & per-split → US4 ranking → US5 aggregates expose → Polish
```

**MVP**: Complete through US1 + US2 + core persistence (run + split rows + aggregates + CLI) + read-only API.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add robustness evaluation cap to `backend/app/config.py` (`leader_follower_robustness_max_evaluations`)
- [X] T002 Document feature stack in `specs/012-leader-follower-rolling-walk-forward-robustness/plan.md` (already aligned with repo)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 [P] Add pure split engine `backend/app/services/rolling_split_utils.py` (calendar months, 0-based split_index)
- [X] T004 [P] Add unit tests `backend/tests/test_rolling_split_utils.py` for non-overlap and exhaustion at `overall_end`
- [X] T005 [P] Add SQLAlchemy models `backend/app/models/leader_follower_robustness_run.py`, `leader_follower_robustness_split_result.py`, `backend/app/models/leader_follower_robustness_aggregate.py`
- [X] T006 [P] Add repositories `backend/app/data/repositories/leader_follower_robustness_run_repo.py`, `leader_follower_robustness_split_result_repo.py`, `leader_follower_robustness_aggregate_repo.py`

---

## Phase 3: User Story 1 — Rolling splits (Priority: P1)

**Goal**: Deterministic month-based split list from overall range + step.

**Independent Test**: Unit tests cover empty/overflow errors and contiguous windows.

- [X] T007 [US1] Wire `validate_walk_forward_windows` for each generated split in `backend/app/services/rolling_split_utils.py`
- [X] T008 [US1] Export `RollingSplitWindows` dataclass and `generate_monthly_rolling_splits` in `backend/app/services/rolling_split_utils.py`

---

## Phase 4: User Story 2 — Grid and candidates (Priority: P1)

**Goal**: Load Mode A grid or Mode B candidates with caps matching `010` philosophy.

**Independent Test**: Service tests with invalid JSON/method and oversize grid/candidate errors.

- [X] T009 [US2] Implement config loading + candidate expansion in `backend/app/services/leader_follower_rolling_robustness_service.py` (`ranking.method` = `rolling_robustness_v1`)
- [X] T010 [US2] Enforce `splits × candidates <= leader_follower_robustness_max_evaluations` in `backend/app/services/leader_follower_rolling_robustness_service.py`

---

## Phase 5: User Story 3 — Per-split metrics (Priority: P2)

**Goal**: For each split × candidate, call `compute_paper_trading_metrics` and persist rows.

**Independent Test**: Mocked metrics in `backend/tests/test_leader_follower_rolling_robustness_service.py` assert row counts and JSON shapes.

- [X] T011 [US3] Implement `run_rolling_robustness_evaluation` loop in `backend/app/services/leader_follower_rolling_robustness_service.py`
- [X] T012 [US3] Persist `LeaderFollowerRobustnessSplitResult` with `config_hash` + bounds in `backend/app/services/leader_follower_rolling_robustness_service.py`

---

## Phase 6: User Story 4 — Cross-split ranking (Priority: P2)

**Goal**: `rolling_robustness_v1` median/consistency score and ranked aggregates.

**Independent Test**: Unit test ranking on synthetic per-split metrics lists in `backend/tests/test_leader_follower_rolling_robustness_service.py`

- [X] T013 [US4] Implement `score_rolling_robustness_v1` and aggregate JSON builder in `backend/app/services/leader_follower_rolling_robustness_service.py`
- [X] T014 [US4] Persist `LeaderFollowerRobustnessAggregate` with deterministic tie-break in `backend/app/services/leader_follower_rolling_robustness_service.py`

---

## Phase 7: User Story 5 — Regime visibility (Priority: P3)

**Goal**: Aggregates expose positive split counts and worst validation return.

**Independent Test**: Aggregate JSON includes `positive_validation_splits`, `worst_validation_cumulative_return_pct`, optional per-split signs.

- [X] T015 [US5] Populate regime summary fields in `aggregate_metrics_json` in `backend/app/services/leader_follower_rolling_robustness_service.py`

---

## Phase 8: CLI + API + integration

- [X] T016 Add Typer command `robustness leader-follower` in `backend/app/cli.py` (grid-file / candidates-file, month windows)
- [X] T017 [P] Add read-only router `backend/app/api/leader_follower_robustness.py` (`/runs`, `/{id}`, `/top-results`, `/splits`)
- [X] T018 Register router and model imports in `backend/app/main.py`
- [X] T019 [P] Add CLI model imports for `init_db` in `backend/app/cli.py`
- [X] T020 [P] Add API tests `backend/tests/test_leader_follower_robustness_api.py`

---

## Phase 9: Polish & cross-cutting

- [X] T021 Run `./scripts/verify.sh` from repo root and fix any failures

---

## Implementation strategy

Ship incrementally: Foundational → service (splits + eval + rank) → CLI → API → verify. Grid + candidates + optional test in one service to avoid partial state.

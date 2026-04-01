# Tasks: 024-strategy-s6-slow-pairs

**Input**: Design documents from `/specs/024-strategy-s6-slow-pairs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Dependency / story order

```text
Setup → Foundational → US1 (core eval) → US2 (CLI preflight single) → US3 (merit/bundle/persist) → Polish
```

## Phase 1: Setup (shared infrastructure)

**Purpose**: Configuration and pure pair math module.

- [x] T001 Add `s6_beta_window_days`, `s6_zscore_window_days`, `s6_regime_min_history_days`, `s6_regime_n_buckets`, `s6_load_buffer_calendar_days` to `backend/app/config.py`
- [x] T002 [P] Create `backend/app/services/s6_slow_pairs.py` with align, OLS, spread, z-feature, and regime helpers per `research.md`

## Phase 2: Foundational (blocking)

**Purpose**: Extend strategy ID and bar minimums before any S6 paths.

- [x] T003 Add `s6` to `StrategyMeritId` and `daily_strategy_min_valid_bars` for `s6` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T004 Import and wire `_compute_s6_window_sample` + `S6WindowSample` dataclass in `backend/app/services/daily_frequency_strategy_research.py`

## Phase 3: User Story 1 — Single-pair evaluation (Priority: P1) MVP

**Goal**: `run_s6_evaluation` returns regime-conditional forward returns on leg A for a fixed leg B.

**Independent Test**: In-memory DB with two symbols + bars; JSON has `by_regime` and no error.

- [x] T005 [US1] Implement `_compute_s6_window_sample` and `run_s6_evaluation` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T006 [US1] Extend `_empty_summary` for `S6_slow_pairs` / `by_regime` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T007 [P] [US1] Add unit tests for pure helpers in `backend/tests/test_s6_slow_pairs.py`

## Phase 4: User Story 2 — Data readiness + single-symbol CLI (Priority: P2)

**Goal**: Preflight and `evaluate daily-strategy s6` with `--leg-b`.

**Independent Test**: Preflight `check` mode passes on synthetic pair data; CLI not required in CI if covered by service tests.

- [x] T008 [US2] Add `assess_daily_strategy_symbol_data` branch for `s6` with `pair_leg_b: str | None` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T009 [US2] Plumb `pair_leg_b` through `run_strategy_eval_data_preflight` / `_assess_all` in `backend/app/services/strategy_eval_data_preflight.py`
- [x] T010 [US2] Add `_daily_strategy_preflight_phase` / `evaluate daily-strategy s6` command with `--leg-b` in `backend/app/cli/commands/evaluate.py`
- [x] T011 [P] [US2] Add preflight + min-bars tests for `s6` in `backend/tests/test_strategy_eval_data_preflight.py`

## Phase 5: User Story 3 — Merit, rolling, bundle, persistence (Priority: P3)

**Goal**: Operator can run pooled merit, rolling rollup, and eval-bundle for `s6` with persistence rows.

**Independent Test**: `run_s6_merit_report` and `run_strategy_merit_bundle` happy paths on synthetic data.

- [x] T012 [US3] Implement `run_s6_merit_report` and `run_s6_merit_rolling_report` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T013 [US3] Extend `run_strategy_merit_bundle` with `pair_leg_b` and `elif strategy == "s6"` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T014 [US3] Register `s6_merit_report` kinds in `backend/app/services/daily_strategy_merit_persistence.py`
- [x] T015 [US3] Add `s6-merit` and `eval-bundle --strategy s6 --leg-b` with validation in `backend/app/cli/commands/evaluate.py`
- [x] T016 [P] [US3] Add `run_s6_evaluation` / merit / bundle tests in `backend/tests/test_daily_frequency_evaluations.py`
- [x] T017 [P] [US3] Add persistence row test for `s6` in `backend/tests/test_daily_strategy_merit_persistence.py`

## Phase 6: Polish

- [x] T018 Mark S6 `implemented` + CLI hint in `backend/app/services/strategy_catalog.py`
- [x] T019 Update module docstring / `StrategyMeritId` consumers text to “S1–S6” where appropriate in `backend/app/services/daily_frequency_strategy_research.py` and `evaluate.py` help strings
- [x] T020 [P] Set **`specs/024-strategy-s6-slow-pairs/spec.md`** status to implemented when CLI ships and **`docs/ROADMAP.md`** task 3.22 line lists S6 implemented

## Parallel execution examples

- **Parallel after T004**: T007 (test_s6_slow_pairs) while implementing T005–T006 if APIs stable.
- **Parallel after T008**: T011 (preflight tests) while T009–T010 land.

## Implementation strategy

Deliver **US1** first (eval + tests), then **US2** (preflight + CLI), then **US3** (merit/bundle/persistence). Run `./scripts/verify.sh` before marking complete.

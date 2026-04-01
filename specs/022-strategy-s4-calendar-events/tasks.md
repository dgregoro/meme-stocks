# Tasks: 022 Strategy S4 — Calendar / scheduled-event flags

**Input**: `/specs/022-strategy-s4-calendar-events/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: plan.md ✓ | spec.md ✓

**Status**: Implementation **complete** on branch `022-strategy-s4-calendar-events`; tasks recorded as done for Speckit audit trail.

## Format: `[ID] [P?] [Story] Description`

## Dependency graph (story order)

```text
Foundational (flags + config) → US1 (eval + assess) → US2 (merit + persistence) → US3 (CLI + catalog + preflight) → Tests + verify
```

**MVP scope**: US1 (single-symbol eval + assess + unit tests for flags).

**Parallel opportunities**: Test files T013–T017 can be authored in parallel after service/CLI Land (different files).

---

## Phase 1: Setup

**Purpose**: Confirm brownfield repo; no new repo initialization.

- [x] T001 Confirm feature paths under `backend/app/` and `specs/022-strategy-s4-calendar-events/` per plan.md

---

## Phase 2: Foundational (blocking)

**Purpose**: Pure helpers + configuration before any eval/merit.

- [x] T002 Add calendar flag helpers in `backend/app/services/s4_calendar_flags.py` (third Friday, OpEx week, month-end, quarter-end, `s4_bucket_label`)
- [x] T003 Add `s4_include_opex_week`, `s4_include_calendar_month_end`, `s4_include_quarter_end_calendar` to `backend/app/config.py`

**Checkpoint**: Foundation ready.

---

## Phase 3: User Story 1 — Single-symbol evaluation (Priority: P1)

**Goal**: Researcher runs `evaluate daily-strategy s4` and gets JSON with `by_bucket` forward-return metrics for calendar buckets.

**Independent Test**: Synthetic `price_data` + stock row → `run_s4_evaluation` returns no `error`, non-zero counts for some bucket over a multi-month window.

- [x] T004 [US1] Add `S4_WINDOW_SAMPLE` types, `S4_BUCKET_KEYS`, `StrategyMeritId` includes `"s4"` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T005 [US1] Implement `_compute_s4_window_sample` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T006 [US1] Implement `run_s4_evaluation` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T007 [US1] Extend `assess_daily_strategy_symbol_data` and `daily_strategy_min_valid_bars` for `"s4"` in `backend/app/services/daily_frequency_strategy_research.py`

---

## Phase 4: User Story 2 — Pooled merit + rolling (Priority: P1)

**Goal**: Pooled S4 merit with baseline, checklist, and rolling excess stability; optional DB persistence.

**Independent Test**: In-memory DB + two symbols + `run_s4_merit_report` → `kind` `s4_merit_report`; rolling → `s4_merit_report_rolling` with `rollup.rolling_pass` bool.

- [x] T008 [US2] Implement `run_s4_merit_report` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T009 [US2] Implement `_rollup_s4_merit_rolling` and `run_s4_merit_rolling_report` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T010 [US2] Extend `run_strategy_merit_bundle` for `strategy == "s4"` in `backend/app/services/daily_frequency_strategy_research.py`
- [x] T011 [US2] Extend `backend/app/services/daily_strategy_merit_persistence.py` for `s4_merit_report` / `s4_merit_report_rolling` / `strategy_merit_bundle` strategy `s4`

---

## Phase 5: User Story 3 — CLI + catalog + preflight (Priority: P1)

**Goal**: Typer commands and operator discoverability match S1–S3.

**Independent Test**: CLI `--help` lists `s4` / `s4-merit`; `eval-bundle --strategy s4` accepted; `strategies list` shows S4 implemented.

- [x] T012 [US3] Register `s4`, `s4-merit`, and `eval-bundle --strategy s4` in `backend/app/cli/commands/evaluate.py`
- [x] T013 [US3] Document S4 in `backend/app/services/strategy_eval_data_preflight.py` (S4 = OHLCV only)
- [x] T014 [US3] Set S4 to `implemented` + `cli_hint` in `backend/app/services/strategy_catalog.py`

---

## Phase 6: Polish & verification

- [x] T015 [P] Add `backend/tests/test_s4_calendar_flags.py`
- [x] T016 [P] Extend `backend/tests/test_daily_frequency_evaluations.py` (S4 eval, merit, rolling, bundle)
- [x] T017 [P] Extend `backend/tests/test_daily_strategy_merit.py` (`_rollup_s4_merit_rolling`)
- [x] T018 [P] Extend `backend/tests/test_daily_strategy_merit_persistence.py` (s4 row build)
- [x] T019 [P] Extend `backend/tests/test_strategy_eval_data_preflight.py` and `backend/tests/test_strategy_catalog.py`
- [x] T020 Add Speckit/docs: `specs/022-strategy-s4-calendar-events/{plan,research,data-model,quickstart}.md`, `contracts/daily-strategy-s4-cli.md`; `docs/ROADMAP.md` task 3.22
- [x] T021 Run `./scripts/verify.sh` (pre-commit + pytest + coverage + container check)

---

## Summary

| Metric | Value |
|--------|------:|
| Total tasks | 21 |
| Completed | 21 |
| US1 tasks | T004–T007, T015–T016 (partial) |
| US2 tasks | T008–T011, T016–T018 |
| US3 tasks | T012–T014, T019 |

All tasks use explicit file paths and checklist ID format per `/speckit.tasks` rules.

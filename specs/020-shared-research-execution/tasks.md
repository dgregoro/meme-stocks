---
description: "Task list for 020 — Shared research execution platform"
---

# Tasks: 020 — Shared research execution platform

**Input**: Design documents from `/home/dgregor/projects/meme-stocks/specs/020-shared-research-execution/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Spec requires backend tests for new logic (PRD / .cursorrules). Story phases include explicit pytest tasks.

**Organization**: Phases follow user story priority; verification tasks cover already-shipped US1–US3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks in the same wave)
- **[Story]**: `[US1]` … `[US5]` for user-story phases
- Paths are repo-relative from `/home/dgregor/projects/meme-stocks/` unless noted

---

## Phase 1: Setup (verify toolchain)

**Purpose**: Confirm environment and baseline tests for spec 020.

- [x] T001 Run `pytest backend/tests/test_research_execution.py -v` from repository root

---

## Phase 2: Foundational (shared package wiring)

**Purpose**: Confirm consumers use `research_execution` per FR-001–FR-003 before extending the package.

- [ ] T002 Confirm `backend/app/services/leader_follower_paper_trading_service.py` imports cost and drawdown helpers from `backend.app.services.research_execution`
- [x] T003 Confirm `backend/app/services/daily_frequency_strategy_research.py` imports `split_calendar_range` / `split_sorted_trading_days` from `backend.app.services.research_execution`

---

## Phase 3: User Story 1 — One cost and drawdown convention (Priority: P1)

**Goal**: Single module for round-trip cost and max drawdown (percent-point space).

**Independent Test**: `pytest backend/tests/test_research_execution.py::test_apply_round_trip_cost backend/tests/test_research_execution.py::test_max_drawdown`

- [x] T004 [US1] Verify `backend/app/services/research_execution/costs.py` and `backend/app/services/research_execution/metrics.py` remain the canonical implementations; run `pytest backend/tests/test_research_execution.py::test_apply_round_trip_cost backend/tests/test_research_execution.py::test_max_drawdown -v` from repository root

---

## Phase 4: User Story 2 — Split evaluation windows consistently (Priority: P1)

**Goal**: Calendar and trading-day chunking in `window_splits.py` only.

**Independent Test**: `pytest backend/tests/test_research_execution.py::test_split_calendar_range_three backend/tests/test_daily_strategy_merit.py::test_calendar_splits_three_segments`

- [x] T005 [US2] Run `pytest backend/tests/test_research_execution.py::test_split_calendar_range_three backend/tests/test_daily_strategy_merit.py::test_calendar_splits_three_segments -v` from repository root

---

## Phase 5: User Story 3 — Run envelope metadata (Priority: P2)

**Goal**: `ResearchRunEnvelope` JSON round-trip for reproducibility fields.

**Independent Test**: `pytest backend/tests/test_research_execution.py::test_research_run_envelope_roundtrip`

- [x] T006 [US3] Run `pytest backend/tests/test_research_execution.py::test_research_run_envelope_roundtrip -v` from repository root

---

## Phase 6: User Story 4 — Generic daily backtest skeleton (Priority: P3)

**Goal**: Long-only, fixed horizon, `same_close` / `next_open` entry on in-memory daily bars; gaps → explicit skip records; net returns use shared cost helpers per `daily-simple-backtest.md`.

**Independent Test**: `pytest backend/tests/test_daily_simple_backtest.py -v`

- [x] T007 [US4] Implement `run_daily_simple_long_only_backtest` and supporting types in `backend/app/services/research_execution/daily_simple_backtest.py`
- [x] T008 [P] [US4] Add `backend/tests/test_daily_simple_backtest.py` covering happy path (known gross), missing-bar skip with structured reason, and net-of-cost path
- [x] T009 [US4] Export the daily backtest API from `backend/app/services/research_execution/__init__.py`

---

## Phase 7: User Story 5 — Walk-forward harness (Priority: P3, FR-006)

**Goal**: Serial harness: window list → callback per window → collected results and per-window errors; `strict=True` re-raises first failure.

**Independent Test**: `pytest backend/tests/test_walk_forward_harness.py -v`

- [x] T010 [US5] Implement `run_walk_forward_windows` (and result types) in `backend/app/services/research_execution/walk_forward_harness.py`
- [x] T011 [P] [US5] Add `backend/tests/test_walk_forward_harness.py` with three synthetic windows and callbacks (success, failure isolation, `strict` mode)
- [ ] T012 [US5] Export harness symbols from `backend/app/services/research_execution/__init__.py`

---

## Phase 8: Polish & cross-cutting

**Purpose**: Docs and full verification.

- [x] T013 [P] Update `docs/ARCHITECTURE.md` to mention `daily_simple_backtest.py` and `walk_forward_harness.py` under shared research execution
- [x] T014 Update `specs/020-shared-research-execution/plan.md` Phase 2 bullets to mark daily backtest + walk-forward harness implemented when T007–T012 complete
- [x] T015 Run `./scripts/verify.sh` from repository root

---

## Dependencies & Execution Order

### Phase dependencies

- Phase 1 → Phase 2 → Phases 3–5 (quick verification; can run 3–5 in parallel after 2)
- Phase 6 (US4) and Phase 7 (US5) depend on Phase 2 completion; **US4 and US5 are independent of each other** after Phase 2
- Phase 8 after Phase 6 and Phase 7

### User story dependencies

| Story | Depends on |
|-------|------------|
| US1–US3 | Foundational verification only |
| US4 | Foundational; uses costs/metrics from `research_execution` |
| US5 | Foundational only (pure orchestration) |

### Parallel opportunities

- T008 and T011 are `[P]` test files vs implementation — run after T007/T010 respectively
- T013 parallel with final test if desired; T014–T015 sequential

### Parallel example: US4 + US5

```bash
# After Phase 2, two developers can implement in parallel:
# Dev A: T007 → T008 → T009
# Dev B: T010 → T011 → T012
```

---

## Implementation Strategy

### MVP

Phases 1–5 restore confidence in shipped core (US1–US3).

### Incremental delivery

1. Complete Phase 6 (US4) → `test_daily_simple_backtest.py` green
2. Complete Phase 7 (US5) → `test_walk_forward_harness.py` green
3. Phase 8 docs + `./scripts/verify.sh`

---

## Notes

- No `specs/020-shared-research-execution/checklists/` present — no checklist gate for `/speckit.implement`.
- CLI for `research backtest …` remains **deferred** (contracts/README.md); call Python API or add a future task if needed.

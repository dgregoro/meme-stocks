# Tasks: 025-strategy-s7-rule-discovery

**Input**: Design documents from `/home/dgregor/projects/meme-stocks/specs/025-strategy-s7-rule-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Dependency / story order

```text
Phase 1 Setup → Phase 2 Foundational → US1 (matrix) → US2 (search + CLI) → US3 (envelope + catalog) → Polish
```

## Phase 1: Setup

- [x] T001 Add `s7_rule_discovery_n_quantiles`, `s7_rule_discovery_max_rules` to `backend/app/config.py`

## Phase 2: Foundational

- [x] T002 Create package `backend/app/services/s7_rule_discovery/__init__.py` exporting public entrypoints

## Phase 3: User Story 1 (P1) — Feature matrix

**Goal**: `build-matrix` produces deterministic CSV from `price_data`.
**Independent test**: DB fixture → CSV rows with non-empty `fwd_*` where bars allow.

- [x] T003 [US1] Implement `build_feature_matrix_rows` and CSV writer in `backend/app/services/s7_rule_discovery/feature_matrix.py`
- [x] T004 [P] [US1] Add matrix build smoke test in `backend/tests/test_s7_rule_discovery.py`

## Phase 4: User Story 2 (P2) — Grid search

**Goal**: Train/test split; quantile rules; `--ack-overfitting-risk` required on CLI.
**Independent test**: Pure grid test on in-memory rows; CLI error without ack.

- [x] T005 [US2] Implement `run_quantile_rule_grid` in `backend/app/services/s7_rule_discovery/grid_search.py`
- [x] T006 [US2] Register `research rule-discovery build-matrix` and `run-search` in `backend/app/cli/commands/research.py`
- [x] T007 [P] [US2] Add grid search unit tests in `backend/tests/test_s7_rule_discovery.py`

## Phase 5: User Story 3 (P3) — Envelope + catalog

**Goal**: JSON includes `ResearchRunEnvelope`; strategy catalog lists S7 CLI.
**Independent test**: Assert `research_envelope` keys in parsed JSON.

- [x] T008 [US3] Attach `ResearchRunEnvelope.from_context` in search JSON assembly in `backend/app/services/s7_rule_discovery/grid_search.py`
- [x] T009 [US3] Set S7 to `implemented` + CLI hint in `backend/app/services/strategy_catalog.py`

## Phase 6: Polish

- [x] T010 Update `docs/ROADMAP.md` task 3.22 line for S7 status
- [x] T011 [P] Mark spec acceptance complete in `specs/025-strategy-s7-rule-discovery/spec.md` if all gates met

## Parallel examples

- After T002: T004 can proceed alongside T003 if API sketch is stable.
- After T005: T007 in parallel with T006 once function signature is fixed.

## Implementation strategy

Ship **US1** (matrix) then **US2** (search + CLI ack), then **US3** (envelope + catalog). Run `./scripts/verify.sh` before completion.

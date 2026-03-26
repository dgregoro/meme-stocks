# Tasks: Leader-Follower Walk-Forward Optimization

**Input**: `specs/010-leader-follower-walk-forward-optimization/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [X] T001 [P] Add `leader_follower_optimization_max_grid_points` to `/home/dgregor/projects/meme-stocks/backend/app/config.py`

## Phase 2: Foundational

- [X] T002 Extract `PaperSimulationMetrics` and `compute_paper_trading_metrics` in `/home/dgregor/projects/meme-stocks/backend/app/services/leader_follower_paper_trading_service.py`; refactor `run_paper_trading_simulation` to reuse core
- [X] T003 [P] Add SQLAlchemy models `LeaderFollowerOptimizationRun`, `leader_follower_optimization_result` in `/home/dgregor/projects/meme-stocks/backend/app/models/leader_follower_optimization_run.py` and `/home/dgregor/projects/meme-stocks/backend/app/models/leader_follower_optimization_result.py`
- [X] T004 [P] Add repositories in `/home/dgregor/projects/meme-stocks/backend/app/data/repositories/leader_follower_optimization_run_repo.py` and `/home/dgregor/projects/meme-stocks/backend/app/data/repositories/leader_follower_optimization_result_repo.py`
- [X] T005 Register models in `/home/dgregor/projects/meme-stocks/backend/app/main.py` and `/home/dgregor/projects/meme-stocks/backend/app/cli.py` imports for `init_db`

## Phase 3: User Story 1 — Run walk-forward optimization (P1)

**Goal**: CLI runs grid over train/validate/(optional) test and persists run + results.
**Independent Test**: CLI with in-memory DB fixture returns run id and result_count > 0.

- [X] T006 [US1] Implement `run_walk_forward_optimization`, split validation, grid expansion, ranking in `/home/dgregor/projects/meme-stocks/backend/app/services/leader_follower_walk_forward_service.py`
- [X] T007 [US1] Add Typer command `optimize leader-follower` in `/home/dgregor/projects/meme-stocks/backend/app/cli.py` with date flags and `--grid-file`

## Phase 4: User Story 2 — Tune parameters (P2)

**Goal**: JSON grid supports `PaperTradingConfig` keys and caps combinations.
**Independent Test**: Unit test rejects grid exceeding max points.

- [X] T008 [US2] Grid JSON parsing and Cartesian product with cap in `/home/dgregor/projects/meme-stocks/backend/app/services/leader_follower_walk_forward_service.py`

## Phase 5: User Story 3 — Rank by robustness (P2)

**Goal**: `walk_forward_v1` scoring documented in research.md.
**Independent Test**: Unit test ranking penalizes train>validate and low trade count.

- [X] T009 [US3] Ranking function and deterministic sort/tie-break in `/home/dgregor/projects/meme-stocks/backend/app/services/leader_follower_walk_forward_service.py`

## Phase 6: User Story 4 — Inspect top results (P3)

**Goal**: Read-only API for runs, detail, top-results.
**Independent Test**: TestClient GETs return 200/404 per contract.

- [X] T010 [US4] Add `/home/dgregor/projects/meme-stocks/backend/app/api/leader_follower_optimization.py` and register router in `/home/dgregor/projects/meme-stocks/backend/app/main.py`

## Phase 7: User Story 5 — Reproducibility (P3)

**Goal**: Stored `config_json` + metrics per period.
**Independent Test**: Two runs with same DB data and config yield same ranks/scores.

- [X] T011 [US5] Persist full `config_json` and `ranking_method` on run; ensure `params_json` frozen per result in `/home/dgregor/projects/meme-stocks/backend/app/services/leader_follower_walk_forward_service.py`

## Phase 8: Polish

- [X] T012 [P] Add `/home/dgregor/projects/meme-stocks/backend/tests/test_leader_follower_walk_forward_service.py`
- [X] T013 [P] Add `/home/dgregor/projects/meme-stocks/backend/tests/test_leader_follower_optimization_api.py`
- [X] T014 Run `/home/dgregor/projects/meme-stocks/scripts/verify.sh` and fix issues

## Dependencies

Setup → Foundational → US1 → US2/US3 (parallel after T006) → US4/US5 → Polish.

## Suggested MVP

T001–T007 (CLI + persistence + core metrics extraction).

## Parallel opportunities

T003,T004 parallel; T012,T013 parallel after T010.

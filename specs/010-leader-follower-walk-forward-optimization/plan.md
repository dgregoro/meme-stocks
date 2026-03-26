# Implementation Plan: Leader-Follower Walk-Forward Optimization

**Branch**: `010-leader-follower-walk-forward-optimization` | **Date**: 2026-03-24  
**Spec**: [spec.md](./spec.md)

## Summary

Add orchestration for walk-forward grid search over `PaperTradingConfig`-compatible parameters, reuse a **non-persistent** paper-trading core for train/validate/test windows, apply a **transparent validation-first** robustness score, persist `LeaderFollowerOptimizationRun` + `LeaderFollowerOptimizationResult`, expose read-only REST routes and `python -m backend.app.cli optimize leader-follower`.

**MVP scope**: Simulation-only parameters (no per-grid-point signal regeneration). Detection-threshold sweeps deferred until an explicit “replay per config” mode exists.

## Technical Context

- **Language/Version**: Python 3.11+
- **Primary dependencies**: FastAPI, SQLAlchemy, Typer, Pydantic (existing stack)
- **Storage**: SQLite; new tables via SQLAlchemy models + `Base.metadata.create_all` (import models in `main.py` / `cli.py`)
- **Testing**: pytest — unit tests for split validation, ranking, grid expansion; integration tests for API + service with in-memory DB
- **Target Platform**: Linux (Fedora), local/container
- **Project Type**: Brownfield backend extension
- **Performance goals**: Modest grid (default cap e.g. 200 combinations from settings); acceptable minutes-long CLI runs on full grid
- **Constraints**: No silent failures; structured API errors; determinism; do not persist one `LeaderFollowerPaperRun` per grid cell

## Constitution Check

*GATE: Pre-implementation*

- [x] Explicit failures — invalid date splits raise validation errors; API 404 uses `error_detail`
- [x] Tests — new service + API covered; `verify.sh` before completion
- [x] Layering — routes delegate to optimization service; repos for persistence
- [x] Scope — research tooling only; no production auto-tuning or live trading
- [x] Reuse — paper trading logic extracted to shared core; no duplicate P&L engine

## Constitution Check (post-design)

- [x] Persistence separate from `leader_follower_paper_runs` clutter
- [x] Ranking formula documented in `research.md` and stored `ranking_method` + weights in `config_json`

## Project Structure

```text
specs/010-leader-follower-walk-forward-optimization/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── optimization-api.md
└── tasks.md

backend/app/
├── models/
│   ├── leader_follower_optimization_run.py
│   └── leader_follower_optimization_result.py
├── data/repositories/
│   ├── leader_follower_optimization_run_repo.py
│   └── leader_follower_optimization_result_repo.py
├── services/
│   ├── leader_follower_paper_trading_service.py  # add metrics core helper
│   └── leader_follower_walk_forward_service.py
├── api/
│   └── leader_follower_optimization.py
├── config.py                    # max grid combinations, default floors
└── cli.py                       # optimize leader-follower

backend/tests/
├── test_leader_follower_walk_forward_service.py
└── test_leader_follower_optimization_api.py
```

**Structure decision**: Single backend tree; mirrors `011` paper-trading patterns.

## Complexity Tracking

None required.

## Phases

- **Phase 0**: [research.md](./research.md) — signal reuse vs replay, ranking formula, grid definition format.
- **Phase 1**: [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md).

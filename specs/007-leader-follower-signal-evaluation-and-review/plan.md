# Implementation Plan: Leader-Follower Signal Evaluation and Review

**Branch**: `007-leader-follower-signal-evaluation-and-review` | **Date**: 2026-03-18
**Spec**: [spec.md](./spec.md)

**Input**: Add a read-only evaluation and review layer for leader-follower signals to measure signal quality and identify strongest/weakest pairs.

## Summary

Implement an evaluation service that computes forward returns for emitted leader-follower signals using existing `LeaderFollowerSignal` and `PriceData`, then exposes read-only APIs (summary, pairs, signals, top/bottom pairs) under `/api/leader-follower/evaluation/`. Evaluation is computed on demand (no persistence). Reuse trading-day logic from `label_service`; add `follower` filter to signal repository.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic
**Storage**: SQLite (existing); reuse `LeaderFollowerSignal`, `PriceData`; no new tables
**Testing**: pytest, TestClient
**Target Platform**: Linux server (backend API)
**Project Type**: Web service (backend API extension)
**Performance Goals**: On-demand evaluation; acceptable for tens to low hundreds of signals
**Constraints**: Read-only; no trading execution; trading-day horizons (1d/3d/5d)
**Scale/Scope**: Brownfield extension; minimal footprint

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Explicit failures over silence** — Missing price data returns `null`; `evaluable_count` exposed.
- [x] **Add/update tests** — New service and API endpoints have tests.
- [x] **Follow existing patterns** — Service layer, repository pattern, API style from `leader_follower.py`.
- [x] **Minimize scope** — Read-only, no schema changes, reuse existing models.
- [x] **Loosely coupled** — Business logic in service; API delegates to service.

## Project Structure

### Documentation (this feature)

```text
specs/007-leader-follower-signal-evaluation-and-review/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/leader_follower.py          # Add evaluation routes
│   ├── services/
│   │   └── leader_follower_evaluation_service.py  # NEW
│   └── data/repositories/
│       └── leader_follower_signal_repo.py  # Add follower, until_date filters
└── tests/
    ├── test_leader_follower_evaluation_service.py  # NEW
    └── test_leader_follower_api.py                 # Add evaluation tests
```

## Complexity Tracking

*No constitution violations requiring justification.*

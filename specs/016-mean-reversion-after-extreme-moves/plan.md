# Implementation Plan: Mean reversion after extreme moves

**Branch**: `016-mean-reversion-after-extreme-moves` | **Date**: 2026-03-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-mean-reversion-after-extreme-moves/spec.md`

## Summary

Add a **research-only** pipeline: detect **close-to-close daily returns** exceeding configurable **up/down** thresholds from `price_data`, persist **`extreme_up` / `extreme_down`** in **`extreme_move_events`**, expose read-only **`/api/extreme-move/*`**, and **Typer** `backfill extreme-move` / `evaluate extreme-move`. Forward returns at **1d / 3d / 5d** trading days reuse **`compute_forward_return`** with anchor **event_date** close (same as 015). Evaluation is **on demand**.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic, Typer
**Storage**: SQLite; new table `extreme_move_events` via SQLAlchemy `Base.metadata.create_all`
**Testing**: pytest; `@pytest.mark.unit` / `@pytest.mark.integration`
**Target Platform**: Linux; existing uvicorn / Podman deployment
**Project Type**: Brownfield `backend/app` API + CLI
**Performance Goals**: Batch backfill acceptable for research
**Constraints**: No look-ahead; structured API errors (PRD Appendix C); additive schema
**Scale/Scope**: One event family; mirror **015 volume-spike** module layout

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| Explicit failures; evaluable_count for missing forwards | Pass |
| Tests for new service/repo/API | Pass |
| Logic in services; thin routes | Pass |
| Minimal scope | Pass |

**Post-design**: No violations.

## Project Structure

### Documentation (this feature)

```text
specs/016-mean-reversion-after-extreme-moves/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code

```text
backend/app/
├── models/extreme_move_event.py
├── data/repositories/extreme_move_event_repo.py
├── services/extreme_move_detection.py
├── services/extreme_move_service.py
├── services/extreme_move_evaluation_service.py
├── api/extreme_move.py
├── config.py
├── main.py
└── cli.py

backend/tests/
├── test_extreme_move_detection.py
├── test_extreme_move_evaluation_service.py
├── test_extreme_move_service.py
└── test_extreme_move_api.py
```

**Structure Decision**: Same as 015: Model → Repository → Service → API; CLI uses `SessionLocal`.

## Complexity Tracking

None.

# Implementation Plan: Volume spike vs baseline signal research

**Branch**: `015-volume-spike-vs-baseline-signal-research` | **Date**: 2026-03-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-volume-spike-vs-baseline-signal-research/spec.md`

## Summary

Add a **research-only** pipeline: detect daily volume spikes vs a rolling baseline from `price_data`, classify `spike_up` / `spike_down` / `spike_flat` from same-day close/close return, persist rows in `volume_spike_events`, expose **read-only** REST under `/api/volume-spike/*`, and **Typer** commands `backfill volume-spike` and `evaluate volume-spike`. Forward returns at **1d / 3d / 5d** trading days use the same convention as `leader_follower_evaluation_service.compute_forward_return` (reference = **event_date** close). Evaluation is **on demand** (no separate forward-return table).

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic, Typer (existing backend stack)  
**Storage**: SQLite; new table `volume_spike_events` via SQLAlchemy `Base.metadata.create_all`  
**Testing**: pytest; `@pytest.mark.unit` for pure math; `@pytest.mark.integration` for API + DB  
**Target Platform**: Linux (Fedora-friendly dev), existing uvicorn deployment  
**Project Type**: Brownfield web API + CLI (`backend/app`)  
**Performance Goals**: Batch backfill acceptable for research (no strict SLA); reuse indexed `price_data` queries  
**Constraints**: No look-ahead (baseline strictly before event day); structured API errors (PRD Appendix C); additive schema only  
**Scale/Scope**: Single new event family; mirror leader-follower evaluation patterns; no ML or paper trading

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| Explicit failures / no silent drops on missing forward prices | Pass — `evaluable_count` per horizon |
| Tests for new service/repo/API | Pass — unit + integration |
| Business logic in services; routes delegate | Pass |
| Minimal scope / minimal diffs | Pass — one table, one router, focused modules |
| Structured API errors | Pass — `raise_api_error` / HTTPException with envelope |

**Re-check post-design**: No violations; no complexity tracking table required.

## Project Structure

### Documentation (this feature)

```text
specs/015-volume-spike-vs-baseline-signal-research/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
backend/app/
├── models/volume_spike_event.py
├── data/repositories/volume_spike_event_repo.py
├── services/volume_spike_detection.py      # pure: baseline, classify, per-day detect
├── services/volume_spike_service.py          # backfill orchestration
├── services/volume_spike_evaluation_service.py  # aggregates; reuses LF forward-return helper
├── api/volume_spike.py
├── config.py                               # volume_spike_research_* settings
├── data/database.py                        # init_db (create_all covers new table)
├── cli.py                                  # backfill volume-spike, evaluate volume-spike
└── main.py                                 # router + model import for metadata

backend/tests/
├── test_volume_spike_detection.py
├── test_volume_spike_evaluation_service.py
└── test_volume_spike_api.py
```

**Structure Decision**: Follow `docs/ARCHITECTURE.md`: Model → Repository → Service → API; CLI calls services with `SessionLocal`. Reuse `PriceDataRepository` and `compute_forward_return` from `leader_follower_evaluation_service`.

## Complexity Tracking

None.

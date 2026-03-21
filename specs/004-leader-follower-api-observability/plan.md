# Implementation Plan: Leader-Follower API Observability

**Branch**: `004-leader-follower-api-observability` | **Date**: 2026-03-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-leader-follower-api-observability/spec.md`

## Summary

Expose leader-follower pipeline internal state through read-only APIs for debugging and evaluation. Add five endpoints (status, runs, leader-events, follower-candidates, enhanced signals with diagnostics) under `/api/leader-follower/`. Persist follower candidates and link leader events to job runs. Scheduler records run at detection start and passes run_id to the pipeline.

## Technical Context

**Language/Version**: Python 3.11+ (existing)
**Primary Dependencies**: FastAPI, SQLAlchemy, existing JobExecutionRepository, LeaderEventRepository, LeaderFollowerSignalRepository
**Storage**: SQLite (existing); new table `leader_follower_candidates`; add `job_run_id` to `leader_events`
**Testing**: pytest, TestClient; existing patterns in `backend/tests/test_leader_follower_api.py`, `test_status_api.py`
**Target Platform**: Linux server (existing backend)
**Project Type**: Web API enhancement
**Performance Goals**: Standard API latency (<500ms p95 for status/runs); no new bottlenecks
**Constraints**: Read-only endpoints; reuse existing auth; minimal schema churn
**Scale/Scope**: Same as current system (~tens of symbols, ~200 runs in history)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| I. Roadmap Alignment | ✅ Phase 3/4 inspectability; ROADMAP candidate |
| II. Explicit Failures Over Silence | ✅ Empty states explicit (no_run, failed, no_leaders, etc.); no fabricated data |
| III. Test Discipline | ✅ New endpoints require tests; existing test patterns apply |
| IV. Skepticism and Honest Reporting | ✅ Spec states limitations; no overclaim |
| V. Jobs Observable | ✅ Run recorded at start; metrics in job_run_history |
| VI. Incremental Development | ✅ Spec → plan → tasks; integrates with existing API/router patterns |

## Project Structure

### Documentation (this feature)

```text
specs/004-leader-follower-api-observability/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # API contracts
│   └── observability-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── leader_follower.py    # Add status, runs, leader-events, follower-candidates; enhance signals
│   ├── models/
│   │   ├── leader_event.py       # Add job_run_id
│   │   └── leader_follower_candidate.py  # NEW
│   ├── data/repositories/
│   │   ├── leader_event_repo.py  # Add run_id filter, list methods
│   │   └── leader_follower_candidate_repo.py  # NEW
│   └── services/
│       ├── leader_follower_service.py  # Accept run_id; persist candidates
│       └── scheduler_service.py       # Record run at start; pass run_id
└── tests/
    └── test_leader_follower_api.py    # Add tests for new endpoints
```

**Structure Decision**: Brownfield. All changes under `backend/app/` and `backend/tests/`. No new top-level directories.

## Implementation Order

1. **P1**: `GET /api/leader-follower/status` — New endpoint; no schema change
2. **P2**: `GET /api/leader-follower/runs` — New endpoint; no schema change
3. **P3**: Add `job_run_id` to `leader_events`; update scheduler to record run at start; `GET /api/leader-follower/leader-events`
4. **P4**: Enhance `GET /api/leader-follower/signals` with diagnostics when empty
5. **P5**: Add `leader_follower_candidates` table; persist in `run_detection`; `GET /api/leader-follower/follower-candidates`

## Key Design Decisions

- **Run-before-detection**: Scheduler inserts a job_run_history row at job start and passes run_id to `run_detection`. On success, update row with metrics; on failure, update with error_message. Enables run_id on leader_events and candidates.
- **Empty diagnostics always**: When `signals=[]`, always include `diagnostics` block regardless of filters (per clarification).
- **metrics_json on candidates**: Store optional screening/lag metrics per candidate for future evaluation (per clarification).

## Complexity Tracking

None. No constitution violations.

# Implementation Plan: Leader Threshold Calibration and Bootstrap Debugging

**Branch**: `006-leader-threshold-calibration-and-bootstrap-debugging` | **Date**: 2026-03-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/006-leader-threshold-calibration-and-bootstrap-debugging/spec.md`

## Summary

Make leader detection inspectable and tunable by exposing symbol-level evaluation data (return_pct, volume_ratio, rejection_reasons), near-miss candidates, and a bootstrap/debug mode with relaxed thresholds. Add `GET /api/leader-follower/leader-debug` and `GET /api/leader-follower/leader-near-miss`; extend runs with date filters and `near_miss_count`. Persist evaluation data in `leader_debug_evaluations` table; add config flags for debug mode and alternate thresholds.

## Technical Context

**Language/Version**: Python 3.11+ (existing)
**Primary Dependencies**: FastAPI, SQLAlchemy, existing leader_follower_service, leader_event_repo, job_run_history
**Storage**: SQLite (existing); new table `leader_debug_evaluations` (run_id, symbol, metrics_json, rejection_reasons); extend metrics_json with `near_miss_count`, `debug_mode`
**Testing**: pytest, TestClient; existing patterns in `backend/tests/test_leader_follower_service.py`, `test_leader_follower_api.py`
**Target Platform**: Linux server (existing backend)
**Project Type**: Web API enhancement + service observability
**Performance Goals**: Standard API latency; evaluation collection adds minimal overhead to run
**Constraints**: Minimal schema churn; no changes to follower logic; debug mode must be explicit in metrics
**Scale/Scope**: ~30 grouped symbols per run; ~50 debug rows per run; historical runs retain debug data for inspection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| I. Explicit Failures Over Silence | ✅ Rejection reasons explicit; no fabricated near-miss data |
| II. Test Discipline | ✅ New endpoints, rejection taxonomy, debug mode require tests |
| III. Jobs Observable | ✅ debug_mode, near_miss_count in run metrics; evaluation data persisted |
| IV. Incremental Development | ✅ Spec → plan → tasks; integrates with existing API/service patterns |
| V. Minimize Scope | ✅ No follower logic changes; debug mode isolated; brownfield constraints respected |

## Project Structure

### Documentation (this feature)

```text
specs/006-leader-threshold-calibration-and-bootstrap-debugging/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # API contracts
│   └── leader-debug-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── leader_follower.py    # Add leader-debug, leader-near-miss; extend runs with since/until, near_miss_count
│   ├── config.py                 # Add leader_follower_debug_mode, debug thresholds
│   ├── models/
│   │   └── leader_debug_evaluation.py  # NEW (run_id, symbol, metrics_json, rejection_reasons)
│   ├── data/
│   │   └── repositories/
│   │       └── leader_debug_repo.py    # NEW
│   └── services/
│       └── leader_follower_service.py  # Collect evaluations; emit rejection reasons; support debug thresholds
└── tests/
    ├── test_leader_follower_service.py # Rejection taxonomy, near-miss, debug mode
    └── test_leader_follower_api.py     # New endpoints
```

**Structure Decision**: Brownfield. All changes under `backend/app/` and `backend/tests/`. No new top-level directories.

## Implementation Order

1. **P1**: Rejection taxonomy + in-run collection in `detect_leaders`; persist to `leader_debug_evaluations`
2. **P2**: Add `GET /api/leader-follower/leader-debug` and `GET /api/leader-follower/leader-near-miss`
3. **P3**: Extend `GET /api/leader-follower/runs` with `since_date`/`until_date` and `near_miss_count`
4. **P4**: Add `leader_follower_debug_mode` + debug thresholds; include `debug_mode` in metrics

## Key Design Decisions

- **Persist evaluations**: Store in `leader_debug_evaluations` table. Compute-on-demand would require re-running detection or replaying from price data; persistence enables historical inspection without recomputation.
- **Debug mode scope**: Global config (env). Per-run override adds complexity; global flag is sufficient for bootstrap calibration.
- **Near-miss default**: 20 symbols; configurable limit parameter on API.
- **Rejection taxonomy**: Fixed set (insufficient_bars, no_data_on_event_date, zero_avg_volume, below_return_threshold, insufficient_volume, error). No free-text.

## Complexity Tracking

None. No constitution violations.

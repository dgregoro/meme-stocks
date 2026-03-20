# Implementation Plan: Leader-Follower Signal Detection

**Branch**: `003-leader-follower-signal-detection` | **Date**: 2026-03-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from specs/003-leader-follower-signal-detection/spec.md (with Clarifications Session 2026-03-19)

## Summary

Leader-follower signal detection identifies stocks that have moved significantly ("leaders") and finds candidate "follower" stocks in the same group that have not yet moved. The system emits structured opportunity signals. **MVP uses price and volume only** from existing `price_data`; no sentiment, no new data ingestion. Key clarifications: (1) Both return % AND volume ratio required for leader; (2) Group mappings in **DB table `stock_groups`**, not config JSON; (3) Strength score = weighted combination of normalized return + volume; (4) Single as-of `event_date` = max `price_data.date` across tracked symbols; (5) Cooldown default = 1 calendar day.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, SQLAlchemy, existing PriceDataRepository, StockRepository, JobExecutionRepository  
**Storage**: SQLite (existing); new tables: `leader_events`, `leader_follower_signals`, `stock_groups`  
**Testing**: pytest, backend/tests/  
**Target Platform**: Linux server (existing backend)  
**Project Type**: Web application (backend service enhancement)  
**Performance Goals**: Job completes within reasonable time for tracked universe (~tens of symbols)  
**Constraints**: Per-symbol failures must not stop job; max_instances=1, coalesce=True for scheduler  
**Scale/Scope**: Same as current system (~tens of tracked symbols)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| I. Roadmap Alignment | ✅ New feature; ROADMAP Phase 3/4 candidate |
| II. Explicit Failures Over Silence | ✅ Per-symbol skip with log; no fabrication |
| III. Test Discipline | ✅ New service, repos, API require tests |
| IV. Skepticism and Honest Reporting | ✅ Testable criteria; no hype |
| V. Reliability and Observability | ✅ Job records run; scheduler safeguards |
| VI. Transparent Assumptions | ✅ event_date rule; primary group rule documented |
| VII. Incremental Delivery | ✅ Feature flag; minimal additions |
| VIII. Specs Fit Architecture | ✅ Model → Repo → Service → API → Tests |
| IX. Bias Against Rewrites | ✅ No client/retry/DI refactor |

## Project Structure

### Documentation (this feature)

```text
specs/003-leader-follower-signal-detection/
├── plan.md              # This file
├── spec.md              # Feature spec (with Clarifications)
├── research.md          # Phase 0 design decisions
├── data-model.md        # Entities and schema
├── quickstart.md        # Validation steps
├── contracts/           # API contract
│   └── leader-follower-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                    # Add leader_follower_* config keys
│   ├── main.py                      # Register models, leader_follower router
│   ├── models/
│   │   ├── leader_event.py          # NEW
│   │   ├── leader_follower_signal.py # NEW
│   │   └── stock_group.py           # NEW
│   ├── data/
│   │   ├── database.py              # Register new models; migration for stock_groups
│   │   └── repositories/
│   │       ├── leader_event_repo.py         # NEW
│   │       ├── leader_follower_signal_repo.py # NEW
│   │       └── stock_group_repo.py         # NEW
│   ├── services/
│   │   ├── leader_follower_service.py # NEW
│   │   └── scheduler_service.py     # Add leader_follower_detection job
│   └── api/
│       └── leader_follower.py       # NEW
└── tests/
    ├── test_leader_follower_service.py  # NEW
    └── test_leader_follower_api.py      # NEW
```

**Structure Decision**: Backend-only. Follows ARCHITECTURE.md: Model → Repository → Service → API → Tests. No frontend changes in MVP.

## Complexity Tracking

None. No constitution violations.

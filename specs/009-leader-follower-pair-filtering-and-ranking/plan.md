# Implementation Plan: Leader-Follower Pair Filtering and Ranking

**Branch**: `009-leader-follower-pair-filtering-and-ranking` | **Date**: 2026-03-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-leader-follower-pair-filtering-and-ranking/spec.md`

## Summary

Add ranking and filtering of leader-follower pairs based on historical evaluation metrics. Reuse existing `run_evaluation` and `aggregate_by_pair` outputs; apply sort and filter on top. New API endpoints (`/pairs/ranked`, `/pairs/filtered`) expose ranked/filtered pairs with transparency (thresholds, pass/fail status). Optional config-driven integration with signal generation behind a feature flag (default off).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic (existing)
**Storage**: SQLite (existing); no new tables for MVP
**Testing**: pytest (existing); add tests in `backend/tests/test_leader_follower_api.py`
**Target Platform**: Linux server (same as rest of backend)
**Project Type**: Web service (backend API extension)
**Performance Goals**: On-demand evaluation; pair count is small (~50–200); O(n) sort/filter is acceptable
**Constraints**: Reuse evaluation logic; no duplication; conservative default thresholds
**Scale/Scope**: ~50–200 pairs; ~50–100 signals; in-memory processing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Explicit failures over silence | ✓ Pass | APIs return empty list or clear error; no silent swallow |
| Add/update tests for backend logic | ✓ Pass | New endpoints require tests |
| Follow existing patterns | ✓ Pass | Reuse evaluation service; business logic in services or API layer (minimal) |
| Minimize scope | ✓ Pass | API-only for MVP; signal integration optional and behind flag |
| Loosely coupled | ✓ Pass | Filter/rank on evaluation output; no new external deps |

## Project Structure

### Documentation (this feature)

```text
specs/009-leader-follower-pair-filtering-and-ranking/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal; no new entities)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (pairs-api.md)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── leader_follower.py      # Add /pairs/ranked, /pairs/filtered
│   ├── config.py                    # Add pair-filtering config keys
│   └── services/
│       ├── leader_follower_evaluation_service.py  # Optional: filter/rank helpers
│       └── leader_follower_service.py            # Optional: allowed-pairs check (when flag on)
└── tests/
    └── test_leader_follower_api.py  # Add tests for new endpoints
```

**Structure Decision**: Brownfield extension. All changes within existing `backend/app` layout. No new modules; extend `leader_follower.py` API and `config.py`.

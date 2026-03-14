# Implementation Plan: Combined Signal Alerts

**Branch**: `002-combined-signal-alerts` | **Date**: 2026-03-13 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from specs/002-combined-signal-alerts/spec.md

## Summary

Add a signal aggregation layer that evaluates multiple signals per ticker (sentiment, price, volume, RSI) and generates alerts only when the combined weighted score meets a configurable threshold. Each alert includes structured metadata explaining which signals fired and their values. The aggregation layer consumes existing detectors without modifying them.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, SQLAlchemy, existing services (activity_detector, pattern_analyzer, sentiment_analyzer)  
**Storage**: SQLite (existing); Notification model extended with metadata field (JSON or similar)  
**Testing**: pytest, backend/tests/  
**Target Platform**: Linux server (existing backend)  
**Project Type**: Web application (backend service enhancement)  
**Performance Goals**: Notification check job completes within existing 30-minute interval  
**Constraints**: No changes to existing detectors; config-driven weights/threshold; per-symbol failures must not stop job  
**Scale/Scope**: Same as current system (~tens of tracked symbols)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| I. Roadmap Alignment | ✅ Phase 2.5, PLAN.md, PRD FR-3.7 |
| II. Explicit Failures Over Silence | ✅ Per-symbol failures logged, no fabrication |
| III. Test Discipline | ✅ New service + aggregation logic require tests |
| IV. Skepticism and Honest Reporting | ✅ Success criteria measurable |
| V. Reliability and Observability | ✅ Job continues on per-symbol failure |
| VI. Transparent Assumptions | ✅ Weights and threshold configurable, no look-ahead |
| VII. Incremental Delivery | ✅ Minimal change: new service, extend Notification, refactor notification_service flow |

## Project Structure

### Documentation (this feature)

```text
specs/002-combined-signal-alerts/
├── plan.md              # This file
├── research.md          # Phase 0 design decisions
├── data-model.md        # Phase 1 entities and schema
├── quickstart.md        # Phase 1 validation steps
├── contracts/           # API contract for notification response
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                    # Add combined_signal_weights, combined_signal_threshold
│   ├── models/
│   │   └── notification.py          # Add signal_metadata column (JSON)
│   ├── services/
│   │   ├── activity_detector.py     # Unchanged (consumed by aggregation)
│   │   ├── pattern_analyzer.py      # Unchanged (consumed for RSI)
│   │   ├── combined_signal_service.py   # NEW: aggregation + scoring
│   │   └── notification_service.py  # Refactor: gather signals → aggregate → create notification
│   └── api/
│       └── notifications.py         # Extend response to include signal_metadata
└── tests/
    └── test_combined_signal_service.py   # NEW
    └── test_notification_service.py      # Update for combined flow
```

**Structure Decision**: Backend-only. Follows existing ARCHITECTURE.md: Service (combined_signal_service) consumes detectors, notification_service orchestrates. No new models beyond Notification schema extension. Data migration for new column (nullable, backward compatible).

## Complexity Tracking

None. No constitution violations.

# Implementation Plan: Leader-Follower Historical Backfill and Replay

**Branch**: `008-leader-follower-historical-backfill-and-replay` | **Date**: 2026-03-23
**Spec**: [spec.md](./spec.md)

**Input**: Replay leader-follower detection across historical dates using Alpaca daily bars to populate PriceData, generate historical signals, and accelerate evaluation.

## Summary

Add a backfill CLI command that replays leader-follower detection for a date range. Use Alpaca `timeframe=1Day` to fetch historical daily bars, persist to PriceData, and run detection per date with `run_detection_for_date`. Support dry-run and persist modes. Replay-generated signals work with existing evaluation APIs.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, SQLAlchemy, Alpaca API (requests), existing AlpacaDataClient
**Storage**: SQLite (PriceData, LeaderFollowerSignal); reuse existing schema
**Testing**: pytest, mock Alpaca where needed
**Target Platform**: Linux server, CLI
**Project Type**: Backend service + CLI extension
**Performance Goals**: Batch Alpaca fetches; avoid blocking on single symbol
**Constraints**: No lookahead; idempotent persist; Alpaca rate limits
**Scale/Scope**: Tens to hundreds of trading days; grouped universe symbols

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Explicit failures over silence** — Log missing data, API failures; surface in summary.
- [x] **Add/update tests** — New replay service and CLI have tests.
- [x] **Follow existing patterns** — Reuse leader_follower_service, PriceDataRepository, AlpacaDataClient.
- [x] **Minimize scope** — No schema changes; extend Alpaca usage for daily bars only.
- [x] **Loosely coupled** — Replay service orchestrates; delegates to existing services.

## Project Structure

### Documentation (this feature)

```text
specs/008-leader-follower-historical-backfill-and-replay/
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
│   ├── clients/alpaca_data_client.py    # Add daily-bar fetch support
│   ├── services/
│   │   ├── leader_follower_replay_service.py  # NEW
│   │   └── leader_follower_service.py   # Add run_detection_for_date
│   └── cli.py                           # Add backfill leader-follower
└── tests/
    └── test_leader_follower_replay_service.py  # NEW
```

## Complexity Tracking

*No constitution violations requiring justification.*

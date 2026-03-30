# Implementation Plan: 020 — Shared research execution platform

**Branch**: `020-shared-research-execution` | **Date**: 2026-03-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-shared-research-execution/spec.md`

## Summary

Deliver **cross-strategy** building blocks: **transaction costs** and **drawdown/equity** helpers, **calendar/trading window splits**, and a **run envelope** for reproducibility. **Refactor** daily-frequency merit and leader-follower paper code to consume the shared package. **Plan** (not yet fully implement) a **daily simple backtest** and **walk-forward harness** per slice specs in this directory.

## Technical Context

**Language/Version**: Python 3.11+ (project std; CI may use 3.12)
**Primary Dependencies**: SQLAlchemy (consumers only), Typer CLI (future commands), existing `PriceDataRepository` for planned backtest
**Storage**: SQLite existing (`daily_strategy_merit_runs` optional envelope embed); no new tables required for core
**Testing**: `pytest`, `./scripts/verify.sh` (pre-commit, bandit, container)
**Target Platform**: Linux (Fedora per project preference); dev on macOS acceptable
**Project Type**: Backend services under `backend/app/services/research_execution/`
**Performance Goals**: N/A for pure helpers; harness/backtest should serialize windows (no parallel v1)
**Constraints**: PRD §5.0 — explicit skips, no silent failures; minimal diffs per constitution
**Scale/Scope**: Personal research scale; ~1k–10k symbols file lists; full JSON merit payloads already tolerated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| Explicit failures / no silent swallow in new simulators | ✅ Required in slice specs |
| Backend tests for new logic | ✅ `test_research_execution.py` + downstream tests |
| Services pattern; repositories for new persistence only when added | ✅ Core is pure functions |
| Minimize scope / no unnecessary infra | ✅ No queues, no new DB for envelope |
| Docs updated | ✅ ARCHITECTURE, ROADMAP, this spec tree |

**Post-design re-check**: No new violations; planned backtest remains service-layer + pytest.

## Phase 0 — Research

**Output**: [research.md](./research.md) — all architectural “NEEDS CLARIFICATION” items resolved.

## Phase 1 — Design & contracts

**Outputs**:

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/README.md](./contracts/README.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Slice specs | [README.md](./README.md) index |

## Phase 2 — Implementation status (stop per /speckit.plan)

**Completed (core)**:

- `backend/app/services/research_execution/` — `costs`, `metrics`, `window_splits`, `run_envelope`, `__init__`
- Refactors: `daily_frequency_strategy_research`, `leader_follower_paper_trading_service`
- Config: `research_default_round_trip_cost_bps`
- Tests: `backend/tests/test_research_execution.py`

**Shipped (service-layer; tests in `backend/tests/`)**:

- Daily simple backtest module ([daily-simple-backtest.md](./daily-simple-backtest.md)) — `research_execution/daily_simple_backtest.py` (Typer CLI still optional / deferred).
- Walk-forward harness ([walk-forward-harness.md](./walk-forward-harness.md)) — `research_execution/walk_forward_harness.py`.

**Still planned**:

- Optional `run_envelope` embed in persisted merit JSON ([run-envelope.md](./run-envelope.md))
- Optional `research backtest …` CLI wiring once DB-backed or file-backed inputs are finalized

## Project Structure

### Documentation (this feature)

```text
specs/020-shared-research-execution/
├── README.md
├── spec.md
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── README.md
├── core-helpers.md
├── run-envelope.md
├── daily-simple-backtest.md
├── walk-forward-harness.md
├── net-metrics-reporting.md
└── integration-conventions.md
```

### Source code (repository root)

```text
backend/app/services/research_execution/
├── __init__.py
├── costs.py
├── metrics.py
├── window_splits.py
└── run_envelope.py

backend/tests/test_research_execution.py
```

**Structure decision**: Single package under `services/`; no new top-level package. Future `daily_simple_backtest.py` colocated in `research_execution/`.

## Complexity Tracking

> No constitution violations requiring justification.

## Agent context

Run after updating this plan:

```bash
SPECIFY_FEATURE=020-shared-research-execution .specify/scripts/bash/update-agent-context.sh cursor-agent
```

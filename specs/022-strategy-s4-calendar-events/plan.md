# Implementation Plan: Daily strategy S4 — Calendar / scheduled-event flags

**Branch**: `022-strategy-s4-calendar-events` | **Date**: 2026-03-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-strategy-s4-calendar-events/spec.md`

**Delivery status**: Core implementation **complete** on this branch (`feat(s4)` commit). This plan documents technical context and design artifacts for Speckit traceability.

## Summary

S4 adds **calendar-derived signal buckets** (OpEx week, calendar month-end, calendar quarter-end) over existing daily **OHLCV** bars, with **forward returns** and the same **research shell** as S1–S3: single-symbol eval, pooled merit + baseline + checklist, rolling excess stability, preflight (`--preflight-only` / `--ensure-data`), optional merit persistence, and `eval-bundle --strategy s4`. No new relational tables; logic lives in `backend/app/services/` and Typer CLI under `evaluate daily-strategy`.

## Technical Context

**Language/Version**: Python 3.11+ (project standard; CI may use 3.12)

**Primary Dependencies**: FastAPI (app), SQLAlchemy (ORM), Typer (CLI), Pydantic / pydantic-settings (`config.py`), existing `PriceDataRepository`, `compute_forward_return` from `leader_follower_evaluation_service`

**Storage**: SQLite `price_data` + `stocks` only for S4; optional `daily_strategy_merit_runs` for persisted merit JSON

**Testing**: `pytest`, `@pytest.mark.unit`; coverage gate on `backend/app` per project rules

**Target Platform**: Linux (Fedora per project preference); local/CI

**Project Type**: Brownfield CLI + service module (no new HTTP routes required for MVP)

**Performance Goals**: Research/offline; no hot-path latency requirement

**Constraints**: No exchange holiday calendar; calendar month-end may not be a trading day (fewer bars than naive calendar count). All three `s4_include_*` false → **explicit** assessment/checklist failure.

**Scale/Scope**: Single-symbol eval and multi-symbol pooled merit; same symbol caps as other daily-strategy ensure-data paths

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | S4 alignment |
|-----------|----------------|
| Explicit failures | Disabled dimensions → `None` sample / checklist message; insufficient bars → structured hints |
| Tests for backend logic | `test_s4_calendar_flags.py`, S4 paths in `test_daily_frequency_evaluations.py`, rollup, persistence, preflight |
| Follow existing patterns | Mirrors S2 bucket merit shape (`by_bucket`), S3 rolling rollup pattern |
| Minimal scope | No FOMC ingest; pure `datetime.date` helpers in dedicated module |
| Services vs routes | Business logic in `daily_frequency_strategy_research.py`; CLI delegates |

**Gate**: PASS — no unjustified violations.

## Project Structure

### Documentation (this feature)

```text
specs/022-strategy-s4-calendar-events/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1 (logical)
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1 — CLI JSON shapes
└── tasks.md             # /speckit.tasks
```

### Source code (repository)

```text
backend/app/services/s4_calendar_flags.py          # Pure calendar helpers
backend/app/services/daily_frequency_strategy_research.py  # S4 sample, eval, merit, rollup, assess
backend/app/services/daily_strategy_merit_persistence.py   # s4_merit_report kinds
backend/app/services/strategy_eval_data_preflight.py        # S4 = OHLCV-only note
backend/app/services/strategy_catalog.py                    # S4 tooling line
backend/app/config.py                                         # s4_include_* settings
backend/app/cli/commands/evaluate.py                          # s4, s4-merit, eval-bundle s4
backend/tests/test_s4_calendar_flags.py
backend/tests/test_daily_frequency_evaluations.py             # S4 eval/merit/bundle tests
backend/tests/test_daily_strategy_merit.py                    # _rollup_s4
backend/tests/test_daily_strategy_merit_persistence.py
backend/tests/test_strategy_eval_data_preflight.py
backend/tests/test_strategy_catalog.py
```

**Structure Decision**: Single backend tree under `backend/app/` consistent with S1–S3; no `src/` top-level.

## Complexity Tracking

No constitution violations requiring justification.

## Phase 2 (Speckit)

Design artifacts below complete Phase 0–1; **`tasks.md`** is produced by `/speckit.tasks` workflow (this session).

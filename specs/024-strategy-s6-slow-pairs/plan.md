# Implementation Plan: 024 — Daily strategy S6 (slow pairs / relative value)

**Branch**: `024-strategy-s6-slow-pairs` | **Date**: 2026-03-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/024-strategy-s6-slow-pairs/spec.md`

## Summary

Add **S6**: a **two-leg slow pair** research track on daily `price_data`. Per day *t*, fit **hedge ratio** (OLS of log(leg A) on log(leg B)) on a **causal trailing window** ending *t−1*, form a **spread residual**, convert to a **rolling z-score** (mean/std of prior residuals only), then assign **expanding quantile regimes** on that z-series (reuse `prior_expanding_quantile_regimes`). Summarize **forward close-to-close returns on leg A** by regime + baseline (same calendar days), with **pooled merit** across many leg‑A tickers sharing one **leg B** (CLI `--leg-b`). No intraday, no live execution.

## Technical Context

**Language/Version**: Python 3.11+ (project standard; CI may use 3.12)
**Primary Dependencies**: FastAPI stack, SQLAlchemy, existing `daily_frequency_strategy_research`, `PriceDataRepository`, `prior_expanding_quantile_regimes`
**Storage**: SQLite `price_data` + `stocks` only (no new tables)
**Testing**: pytest; unit tests for pure math + in-memory DB smoke tests; no network
**Target Platform**: Linux (Fedora per project preference)
**Project Type**: backend research CLI + services under `backend/app/`
**Performance Goals**: N/A (batch research)
**Constraints**: Causal windows only for beta and z; explicit hints when overlap or history insufficient; follow PRD reliability (no silent failures)
**Scale/Scope**: Explicit pair list via `--leg-b` + `--symbols` / `--symbol`; MVP does not model corporate actions in prices (documented limitation)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| Explicit failures / structured hints for missing data | ✅ Design uses existing `_price_data_hint`, S6-specific messages |
| Tests for new backend logic | ✅ Required in tasks |
| Minimal scope / follow ARCHITECTURE patterns | ✅ New `s6_slow_pairs.py` + extensions to existing research module |
| No fabricated defaults | ✅ None where history missing; regimes None until history |

**Post-design**: No new violations; pair MVP documents CA/split limitation in research.md.

## Project Structure

### Documentation (this feature)

```text
specs/024-strategy-s6-slow-pairs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── daily-strategy-s6-cli.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/app/
├── config.py                          # s6_* settings
├── services/
│   ├── s6_slow_pairs.py               # align, beta, spread, z, feature maps (NEW)
│   └── daily_frequency_strategy_research.py  # S6 assess, eval, merit, bundle
├── services/strategy_eval_data_preflight.py
├── services/daily_strategy_merit_persistence.py
├── services/strategy_catalog.py
└── cli/commands/evaluate.py
backend/tests/
├── test_s6_slow_pairs.py
├── test_daily_frequency_evaluations.py   # S6 eval + merit hooks
├── test_strategy_eval_data_preflight.py
└── test_daily_strategy_merit_persistence.py
```

**Structure Decision**: Same as S1–S5: dedicated small service module + centralized daily-frequency research orchestration + CLI under `evaluate daily-strategy`.

## Complexity Tracking

> N/A — no constitution violations requiring justification.

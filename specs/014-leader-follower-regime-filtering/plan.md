# Implementation Plan: Leader-follower regime filtering

**Branch**: `014-leader-follower-regime-filtering` | **Date**: 2026-03-27 | **Spec**: [spec.md](./spec.md)

## Summary

Add optional **market regime gating** to leader-follower paper execution: benchmark (default **SPY**) **close vs MA** and optional **rolling volatility** threshold on benchmark returns, optional **AND** with existing **013** sector confirmation; persist **regime snapshot** on `leader_follower_paper_trades`; extend **`PaperTradingConfig`**, **`PaperSimulationMetrics`**, run-level skip counter, **`ALLOWED_GRID_KEYS`**, API/CLI. Default **off**; conservative **fail** when regime enabled but benchmark data insufficient.

## Technical Context

**Language/Version**: Python 3.11
**Dependencies**: SQLAlchemy, FastAPI, `PriceDataRepository`, existing `PaperTradingConfig`, `sector_confirmation_service` (013)
**Storage**: SQLite; additive columns on `leader_follower_paper_trades`, `leader_follower_paper_runs`; `_migrate_*` in `database.py`
**Testing**: pytest—pure regime feature math; paper trading integration with mocked prices; config validation tests
**Target**: Linux; align date/UTC conventions with 013 entry-date resolution

## Constitution Check

| Gate | Status |
|------|--------|
| Explicit failures | Log warnings; skip trades when data missing and regime enabled; validation errors for invalid config |
| Tests | New `test_regime_filter_service.py` (or similar) + extend paper trading tests |
| Patterns | Prefer `regime_filter_service.py` (pure evaluation + repo) wired in `leader_follower_paper_trading_service` |
| Minimal scope | No ML; no new tables; benchmark from existing `price_data` only |

**Post-design**: Gate **order** is **sector then regime** (documented in `research.md` / `quickstart.md`). Rolling vol uses **population** std of simple daily returns (`statistics.pstdev` over `volatility_window`).

## Project Structure

```text
specs/014-leader-follower-regime-filtering/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── paper-trading-regime-fields.md
├── tasks.md
└── spec.md

backend/app/
├── services/
│   ├── regime_filter_service.py          # NEW: evaluate regime, snapshot dict
│   └── leader_follower_paper_trading_service.py  # wire gate, metrics
├── services/leader_follower_walk_forward_service.py  # ALLOWED_GRID_KEYS
├── models/leader_follower_paper_trade.py
├── models/leader_follower_paper_run.py
├── data/database.py
├── api/leader_follower_paper_trading.py
└── cli.py                                 # optional flags mirror 013 pattern

backend/tests/
├── test_regime_filter_service.py
└── test_leader_follower_paper_trading_service.py  # regime gate cases
```

**Structure Decision**: Brownfield `backend/app`; reuse 013 patterns for migrations and API field adds.

## Complexity Tracking

| Item | Note |
|------|------|
| Gate ordering with 013 | Single documented order; separate skip counters |
| Volatility units | Fixed in research for reproducibility |

## Phase 0/1 artifacts

- `research.md`: benchmark defaults, return definition, fail vs pass on missing data, interaction when sector sub-flag set without 013 enabled.
- `data-model.md`: exact column names and JSON keys.
- `contracts/paper-trading-regime-fields.md`: API field list and types.
- `quickstart.md`: example grid snippet + simulate CLI.

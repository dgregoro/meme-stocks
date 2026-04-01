# Implementation Plan: 025 — S7 rule discovery (bounded)

**Branch**: `025-strategy-s7-rule-discovery` | **Date**: 2026-03-31 | **Spec**: [spec.md](./spec.md)

## Summary

Deliver **opt-in** `research rule-discovery` commands that build a **versioned daily feature matrix** from `price_data` and run a **pre-registered, bounded single-split grid** of threshold rules on one forward horizon. Results include `ResearchRunEnvelope` metadata and explicit **multiple-testing / overfitting** warnings. **No** `eval-bundle` / `daily-strategy` integration in this slice (per prior plan + spec).

## Technical Context

**Language/Version**: Python 3.11+ (CI may use 3.12)
**Primary Dependencies**: FastAPI stack (existing), SQLAlchemy, Typer, pydantic-settings, existing `PriceDataRepository`, `DailyBar` / `bars_from_price_rows`, `realized_vol_series`, `volume_log_z_series` from `daily_frequency_strategy_research`
**Storage**: SQLite `price_data` only for matrix build; search consumes CSV/JSON matrix files under `research_dataset_dir` policy (operator paths)
**Testing**: pytest; `@pytest.mark.unit` for pure search + matrix math; DB smoke optional
**Target Platform**: Linux / local CLI
**Project Type**: backend service module + Typer subcommands under `research`
**Performance Goals**: Cap candidate rules via config (`s7_rule_discovery_max_rules`); refuse oversized grids
**Constraints**: Strict date split: thresholds from **train** dates only; test metrics on **hold-out** dates only; require `--ack-overfitting-risk`
**Scale/Scope**: Single-symbol matrix MVP; multi-symbol extension later

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| Explicit failures | Clear errors for missing bars, bad dates, missing ack flag |
| Tests for new backend logic | Unit tests for search + matrix rows |
| Minimal scope | No new DB tables; no eval-bundle wiring |
| Reliability / no silent failures | Log rule counts; stderr banner on CLI |
| Reproducible transforms | Deterministic feature columns + documented horizons |

**Re-check post-design**: PASS — file outputs + envelope; no API surface.

## Project Structure

### Documentation (this feature)

```text
specs/025-strategy-s7-rule-discovery/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code

```text
backend/app/
├── config.py                          # s7_rule_discovery_* settings
├── services/s7_rule_discovery/
│   ├── __init__.py
│   ├── feature_matrix.py              # DB → row dicts / CSV
│   └── grid_search.py                 # train/test split + quantile rules
└── cli/commands/research.py           # rule-discovery typer group

backend/tests/
└── test_s7_rule_discovery.py
```

**Structure Decision**: New package `s7_rule_discovery` (isolated from S1–S6 merit paths).

## Complexity Tracking

> N/A — no constitution violations.

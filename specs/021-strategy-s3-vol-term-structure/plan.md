# Implementation plan: 021 — Strategy S3 (volatility term structure)

**Branch:** `021-strategy-s3-vol-term-structure`
**Date:** 2026-03-29
**Spec:** [spec.md](./spec.md)

## Summary

Add **macro vol term-structure** inputs (VIX + longer-dated index), **persist** daily observations, **label regimes** with pre-registered rules, and expose **evaluation + merit** paths parallel to **S1/S2** (`evaluate daily-strategy s3`, `s3-merit`, `eval-bundle --strategy s3`). External fetches go through **`backend/app/clients/`** with shared retry/error typing (PRD §5.0).

## Technical context

| Area | Choice |
|------|--------|
| Language | Python 3.11+ |
| Storage | SQLite; new table(s) for macro series (see spec data model) |
| Equity data | Existing `price_data` + 019 preflight / `--ensure-data` |
| CLI | Typer under `backend/app/cli/commands/evaluate.py` |
| Shared math | `research_execution` for merit window splits, costs, envelope (020) |

## Phases (high level)

1. **Client + config** — Provider(s) for VIX / VIX3M (or documented proxy); env-driven keys; no hard-coded secrets.
2. **Model + repository + ingestion** — Idempotent daily upsert; explicit gaps (no interpolation).
3. **Regime service** — Pure functions: spread/ratio → regime id; train/hold-out policy documented.
4. **Evaluation + merit** — Mirror S1/S2 structure in `daily_frequency_strategy_research.py` (or extracted submodule); pooled buckets vs baseline; checklist hooks.
5. **Tests** — Unit tests with fixtures/mocks; integration optional mock server.
6. **Catalog** — Update `strategy_catalog.py` S3 tooling to `implemented` when CLI ships.

## Constitution / reliability

- No silent failures on provider errors; typed exceptions + logging.
- Missing macro or equity bar → skip with reason in eval JSON (not fabricated OHLCV).
- Scheduler job (if any): `max_instances=1`, `coalesce=True`, misfire grace documented.

## Out of scope (plan level)

- HMM / ML regime models in v1.
- Intraday VIX or options surface.
- Live trading or alerts.

# Quickstart: 022 Strategy S4 (calendar flags)

**Status:** Implemented — example commands for local research.

## Prerequisites

- `stocks` row and `price_data` daily bars (e.g. `seed stocks`, `backfill daily-prices`).
- No macro series required (unlike S3).

## Commands

```bash
# Single-symbol exploratory JSON
python -m backend.app.cli evaluate daily-strategy s4 --symbol SPY \
  --start 2024-01-01 --end 2024-12-31

# Pooled merit + checklist (multi-symbol)
python -m backend.app.cli evaluate daily-strategy s4-merit \
  --start 2024-02-01 --end 2024-06-30 --symbols SPY,QQQ

# Rolling stability (calendar splits)
python -m backend.app.cli evaluate daily-strategy s4-merit \
  --start 2024-01-01 --end 2024-12-31 --symbols SPY --splits 4 --split-mode calendar

# One-shot bundle (single window + optional rolling)
python -m backend.app.cli evaluate daily-strategy eval-bundle --strategy s4 \
  --start 2024-02-01 --end 2024-05-31 --symbols SPY --rolling-splits 5 --split-mode trading

# Read-only data readiness (exit 2 if not ready)
python -m backend.app.cli evaluate daily-strategy s4 --symbol SPY --preflight-only
```

## Configuration

Environment / `config.py` fields:

- `s4_include_opex_week` (default true)
- `s4_include_calendar_month_end` (default true)
- `s4_include_quarter_end_calendar` (default true)

See [docs/STRATEGY_TESTING_PLAN.md](../../docs/STRATEGY_TESTING_PLAN.md) for methodology and checklist interpretation.

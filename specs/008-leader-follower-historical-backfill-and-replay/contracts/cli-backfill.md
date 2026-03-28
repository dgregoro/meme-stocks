# CLI Backfill Contract

**Feature**: 008-leader-follower-historical-backfill-and-replay
**Command**: `python -m backend.app.cli backfill leader-follower`

## Invocation

```bash
python -m backend.app.cli backfill leader-follower --start YYYY-MM-DD --end YYYY-MM-DD [--dry-run] [--replace-range]
```

## Arguments

| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| --start, -s | Yes | — | Start date (inclusive) |
| --end, -e | Yes | — | End date (inclusive) |
| --dry-run | No | False | Compute metrics only; do not persist signals |
| --replace-range | No | False | Delete existing signals in [start,end] before replay (use with care) |

## Behavior

1. Validate start <= end.
2. Ensure stock_groups populated; exit with clear message if empty.
3. Backfill PriceData from Alpaca for grouped symbols over [start - lookback, end]. Lookback = 10 trading days (for MIN_BARS_FOR_LEADER + buffer).
4. For each trading day D in [start, end]:
   - Run leader detection for event_date=D
   - Select followers, create signals (respect cooldown)
   - In persist: insert if not exists; count skipped
   - In dry-run: simulate; update in-memory cooldown
5. Print summary to stdout.

## Output (stdout)

```
Backfill leader-follower: 2024-01-02 to 2024-03-15
Days processed: 52
Days skipped: 0
Leaders detected: 18
Candidates found: 42
Signals emitted: 12
Signals skipped (duplicate): 2
Warnings: []
Errors: []
```

## Exit Codes

- 0: Success (including dry-run)
- 1: Validation error (invalid dates, empty stock_groups)
- 2: Alpaca not configured or fetch failed
- 3: Other runtime error

## Prerequisites

- Alpaca API keys (ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY) for data fetch
- Stock groups seeded: `python -m backend.app.cli seed stock-groups`
- Database initialized

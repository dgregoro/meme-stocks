# Quickstart: Leader-Follower Historical Backfill

**Feature**: 008-leader-follower-historical-backfill-and-replay

## Prerequisites

- Stocks seeded: `python -m backend.app.cli seed stocks`
- Stock groups seeded: `python -m backend.app.cli seed stock-groups`
- Alpaca API keys set: `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`
- Database initialized

## Verification Steps

### 1. Dry-run (no persist)

```bash
python -m backend.app.cli backfill leader-follower --start 2024-06-01 --end 2024-06-30 --dry-run
```

Expect: Summary with days_processed, leaders_detected, signals_emitted. No DB writes.

### 2. Persist (small range)

```bash
python -m backend.app.cli backfill leader-follower --start 2024-06-01 --end 2024-06-07
```

Expect: Signals written to leader_follower_signals. Summary printed.

### 3. Verify evaluation includes replay signals

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/summary?since_date=2024-06-01&until_date=2024-06-30" | jq .
```

Expect: total_signals includes backfilled signals; by_horizon shows evaluable counts.

### 4. Idempotent rerun

```bash
python -m backend.app.cli backfill leader-follower --start 2024-06-01 --end 2024-06-07
```

Expect: signals_skipped_duplicate > 0; no new duplicates.

## Empty Stock Groups

If stock_groups is empty, backfill exits with message:

```
Error: stock_groups is empty. Run: python -m backend.app.cli seed stock-groups
```

## Missing Alpaca Keys

If Alpaca keys not set, backfill exits with clear error (do not fail silently).

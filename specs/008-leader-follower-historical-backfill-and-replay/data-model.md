# Data Model: Leader-Follower Historical Backfill

**Feature**: 008-leader-follower-historical-backfill-and-replay
**Date**: 2026-03-23

## No New Persistent Entities

Replay uses existing `PriceData` and `LeaderFollowerSignal`. No new tables.

## Existing Entities Used

### PriceData

Populated by Alpaca daily bar backfill for replay symbols and date range. Same schema as live (stock_symbol, date, open, high, low, close, volume).

### LeaderFollowerSignal

Replay writes same structure as live. Evaluation APIs consume identically. Optional `metrics_json` could store `{"source":"replay"}` later; defer for MVP.

### StockGroup

Unchanged. Replay uses `stock_group_repo.get_all_symbols()` for universe.

## In-Memory / Transient Structures

### ReplaySummary (service output)

| Field | Type | Purpose |
|-------|------|---------|
| days_processed | int | Trading days replayed |
| days_skipped | int | Dates skipped (no data, etc.) |
| leaders_detected | int | Total leader events |
| candidates_found | int | Total follower candidates |
| signals_emitted | int | Signals created |
| signals_skipped_duplicate | int | Idempotent skips |
| missing_data_warnings | list[str] | Dates/symbols with insufficient bars |
| errors | list[str] | API or other failures |

### Dry-Run Cooldown State

`dict[tuple[str, str], date]` — (leader, follower) -> last signal_date. Updated when a dry-run "would emit" a signal.

## Validation Rules

- start_date <= end_date
- Alpaca credentials required for backfill (fail fast if missing)
- Stock groups must exist; empty universe returns early with clear message

# Data Model: Grouped Leader Universe for Leader-Follower

**Feature**: 005-grouped-leader-universe-for-leader-follower
**Date**: 2026-03-22

## 1. No Schema Changes

This feature does not add or modify database tables. It uses existing entities:

- **stock_groups** — Source of the grouped leader universe (existing)
- **stocks** — Full universe; used for `input_universe_size` (existing)
- **job_run_history** — `metrics_json` extended with `grouped_leader_universe_size` (existing column; new key in JSON)

## 2. Repository Change

### StockGroupRepository

**New method**: `get_all_symbols() -> list[str]`

Returns distinct `stock_symbol` values from `stock_groups`, ordered lexicographically. Used as the leader-eligibility set for `detect_leaders`.

```python
def get_all_symbols(self) -> list[str]:
    """Return distinct symbols present in any group, ordered."""
    stmt = select(StockGroup.stock_symbol).distinct().order_by(StockGroup.stock_symbol)
    rows = self._session.execute(stmt).scalars().all()
    return [r for r in rows]
```

**No new entities.** No migrations.

## 3. metrics_json Extension

### job_run_history.metrics_json (existing)

**New key**: `grouped_leader_universe_size` (int)

```json
{
  "input_universe_size": 1601,
  "grouped_leader_universe_size": 30,
  "leader_events_detected": 2,
  "follower_candidates_found": 4,
  "signals_emitted": 0,
  "symbols_skipped": 0,
  "errors_count": 0
}
```

When grouped universe is empty:
```json
{
  "input_universe_size": 1601,
  "grouped_leader_universe_size": 0,
  "leader_events_detected": 0,
  "follower_candidates_found": 0,
  "signals_emitted": 0,
  "symbols_skipped": 0,
  "errors_count": 0
}
```

## 4. In-Memory / Runtime Only

- **Grouped leader universe**: Derived at runtime from `stock_group_repo.get_all_symbols()`. Not persisted as a separate structure.
- **Leader eligibility**: `detect_leaders` iterates over grouped symbols instead of `stock_repo.list()`.

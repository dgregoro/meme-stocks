# 010: Event-Level Evaluation

**Status**: Implemented (2026-03-18)

## Problem

Leader-follower signals are **event-driven**: one strong leader move triggers many follower signals on the same date. Per-signal metrics (win rate, avg return) are **inflated by correlation**—10 wins from 1 event ≠ 10 independent wins.

## Solution

**Event = (leader_symbol, signal_date)**. For each event:
1. Average follower returns across all signals in that event → event return
2. Event wins if event return > 0
3. Aggregate: event_win_rate, event_avg_return_pct, event_count per horizon

## Implementation

- `_aggregate_by_event()` in `leader_follower_evaluation_service.py`
- `GET /evaluation/summary` extended with:
  - `total_events`, `events_per_day`
  - `by_event`: per-horizon `event_win_rate`, `event_avg_return_pct`, `event_count`

## Usage

```bash
curl -s "http://localhost:8000/api/leader-follower/evaluation/summary" | jq '.by_event'
```

Compare `by_horizon` (signal-level) vs `by_event` (event-level). If event-level metrics remain positive, the edge is real rather than correlation illusion.
